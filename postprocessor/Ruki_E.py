# -*- coding: UTF-8 -*-
# Copyright 2025 - Ruki Project
#
# Ruki-E (Extractor) v1.1 - Post Processor for RoboDK
# Extracts all program data to a universal intermediate representation (.ruki)
#
# ----------------------------------------------------
# CHANGELOG v1.1:
#   - Padronizado TODAS as unidades angulares em GRAUS (sem conversões)
#   - INCLUDE_MATRICES = True por default (mais dados para emitters)
#   - Removido timestamps dos steps (eram todos iguais, inúteis)
#   - initial_state agora é snapshot real do início do programa
#   - Removido frame "base" implícito (só "world" é implícito)
#   - Corrigido pose_format para consistência (tudo xyzrpw_mm_deg)
#   - Adicionada documentação de convenções de transformação
#
# ----------------------------------------------------
# CONVENÇÕES DE TRANSFORMAÇÃO (importante para emitters):
#
#   setFrame.pose    = T_world→frame  (pose do frame em relação ao world)
#   setTool.pose     = T_flange→tcp   (pose do TCP em relação ao flange)
#   MoveX.pose       = T_frame→tcp    (pose do TCP em relação ao frame ativo)
#   MoveX.joints     = ângulos das juntas em GRAUS
#   config_RLF       = [REAR, LOWER_ARM, FLIP] onde 0=front/upper/non-flip
#
# ----------------------------------------------------
# More information about RoboDK Post Processors:
#     https://robodk.com/doc/en/Post-Processors.html
#     https://robodk.com/doc/en/PythonAPI/postprocessor.html
# ----------------------------------------------------
#
# INSTALLATION:
#   1. Copy this file to C:/RoboDK/Posts/
#   2. In RoboDK, right-click your program -> Select Post Processor -> Ruki_E
#   3. Generate program - it will create a .ruki JSON file
#
# ----------------------------------------------------

# Request target names and external axes poses from RoboDK
RDK_COMMANDS = {
    "ProgMoveNames": "1",           # Export target names
    "ProgMoveExtAxesPoses": "1",    # Export external axes poses
}

import json
import os
from datetime import datetime, timezone

# Import RoboDK tools
try:
    from robodk import robomath
    from robodk import robofileio
    from robodk import robodialogs
    ROBODK_AVAILABLE = True
except ImportError:
    try:
        # Fallback for older RoboDK versions
        import robodk as robomath
        robofileio = None
        robodialogs = None
        ROBODK_AVAILABLE = True
    except ImportError:
        # Running standalone without RoboDK - create minimal mocks
        ROBODK_AVAILABLE = False
        robomath = None
        robofileio = None
        robodialogs = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def pose_to_xyzrpw_deg(pose):
    """
    Convert RoboDK Mat (4x4) to [x, y, z, rx, ry, rz] in mm and DEGREES.
    Returns None if pose is None.
    
    This is the ONLY pose conversion function used - everything in degrees.
    """
    if pose is None:
        return None
    
    try:
        if ROBODK_AVAILABLE:
            x, y, z, rx, ry, rz = robomath.pose_2_xyzrpw(pose)
        else:
            # Mock: assume pose is already a list [x,y,z,rx,ry,rz]
            x, y, z, rx, ry, rz = pose[0], pose[1], pose[2], pose[3], pose[4], pose[5]
        return [x, y, z, rx, ry, rz]
    except:
        return None


def pose_to_matrix(pose):
    """
    Convert RoboDK Mat (4x4) to a 4x4 list of lists.
    Returns None if pose is None.
    """
    if pose is None:
        return None
    
    try:
        if ROBODK_AVAILABLE:
            matrix = []
            for i in range(4):
                row = []
                for j in range(4):
                    row.append(float(pose[i, j]))
                matrix.append(row)
            return matrix
        else:
            # Mock: return identity matrix
            return [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]
    except:
        return None


def joints_to_list(joints):
    """
    Convert joints to a list of floats.
    RoboDK passes joints in DEGREES to post processors.
    """
    if joints is None:
        return None
    
    try:
        return [float(j) for j in joints]
    except:
        return None


def config_to_list(conf_RLF):
    """
    Convert RoboDK configuration [REAR, LOWER-ARM, FLIP] to list.
    [0,0,0] = [front, upper arm, non-flip]
    """
    if conf_RLF is None:
        return None
    
    try:
        return [int(c) for c in conf_RLF]
    except:
        return None


def filter_name(name):
    """Create a valid file/program name."""
    if robofileio:
        return robofileio.FilterName(name)
    # Fallback
    valid = ''
    for c in str(name):
        if c.isalnum() or c in '_-':
            valid += c
        else:
            valid += '_'
    return valid


# ============================================================================
# RUKI-E POST PROCESSOR CLASS
# ============================================================================

class RobotPost(object):
    """
    Ruki-E (Extractor) Post Processor v1.1
    
    Extracts all available data from RoboDK programs into a universal
    intermediate representation (.ruki JSON format).
    
    UNIT CONVENTIONS (all angles in DEGREES):
    - joints: degrees
    - pose rotation (rx, ry, rz): degrees  
    - speed_linear: mm/s
    - speed_joints: deg/s
    - accel_linear: mm/s²
    - accel_joints: deg/s²
    - positions (x, y, z): mm
    - rounding/blend: mm
    
    TRANSFORMATION CONVENTIONS:
    - setFrame.pose: T_world→frame
    - setTool.pose: T_flange→tcp
    - MoveX.pose: T_frame→tcp
    """
    
    # ==========================================================================
    # PUBLIC VARIABLES (editable by user in RoboDK)
    # ==========================================================================
    
    # Output file extension
    PROG_EXT = 'ruki'
    
    # Schema version for the .ruki format
    SCHEMA_VERSION = '1.1'
    
    # Ruki-E version
    RUKI_VERSION = '1.1.0'
    
    # Include full 4x4 matrices in addition to xyzrpw (recommended: True)
    INCLUDE_MATRICES = True
    
    # Pretty print JSON (indented) or compact
    PRETTY_PRINT = True
    
    # ==========================================================================
    # PRIVATE VARIABLES
    # ==========================================================================
    
    def __init__(self, robotpost='', robotname='', robot_axes=6, *args, **kwargs):
        """
        Initialize the Ruki-E post processor.
        
        Parameters from RoboDK:
            robotpost: Name of the post processor
            robotname: Name of the robot
            robot_axes: Number of axes (including external)
            
        Optional kwargs:
            axes_type: List of axis types ('R'=rotary, 'T'=translation, 'J'=ext rotary, 'L'=ext linear)
            native_name: Original robot name before any rename
            ip_com: Robot IP address
            api_port: RoboDK API port
            prog_ptr: Program item pointer
            robot_ptr: Robot item pointer
            pose_turntable: Turntable offset pose
            pose_rail: Linear rail offset pose
            lines_x_prog: Max lines per program
            pulses_x_deg: Pulses per degree for each axis
        """
        
        # Store constructor parameters
        self.ROBOT_POST = robotpost
        self.ROBOT_NAME = robotname
        self.ROBOT_AXES = robot_axes
        
        # Parse optional parameters
        self.AXES_TYPE = kwargs.get('axes_type', None)
        self.NATIVE_NAME = kwargs.get('native_name', robotname)
        self.IP_COM = kwargs.get('ip_com', None)
        self.API_PORT = kwargs.get('api_port', None)
        self.PROG_PTR = kwargs.get('prog_ptr', None)
        self.ROBOT_PTR = kwargs.get('robot_ptr', None)
        self.POSE_TURNTABLE = kwargs.get('pose_turntable', None)
        self.POSE_RAIL = kwargs.get('pose_rail', None)
        self.MAX_LINES_X_PROG = kwargs.get('lines_x_prog', None)
        self.PULSES_X_DEG = kwargs.get('pulses_x_deg', None)
        
        # Target name (set by RoboDK before MoveJ/L/C calls when ProgMoveNames=1)
        self._TargetName = None
        self._TargetNameVia = None  # For MoveC intermediate point
        
        # External axes poses (set by RoboDK when ProgMoveExtAxesPoses=1)
        self._PoseTrack = None      # Linear track pose
        self._PoseTurntable = None  # Turntable pose
        
        # Program state
        self.PROG_NAME = ''
        self.PROG_NAMES = []
        self.PROG_FILES = []
        self.LOG = ''
        
        # =======================================================================
        # RUKI IR DATA STRUCTURES
        # =======================================================================
        
        # Frames (reference frames / work objects)
        # Only "world" is implicit - others are created by setFrame
        self.frames = {
            "world": {
                "parent": None,
                "pose": [0, 0, 0, 0, 0, 0],
                "pose_format": "xyzrpw_mm_deg",
                "_meta": {"kind": "implicit", "source": "ruki_default"}
            }
        }
        
        # Tools (TCP definitions)
        # Only "tool0" is implicit - others are created by setTool
        self.tools = {
            "tool0": {
                "tcp_pose": [0, 0, 0, 0, 0, 0],
                "pose_format": "xyzrpw_mm_deg",
                "payload_mass": 0,
                "payload_cog": [0, 0, 0],
                "_meta": {"kind": "implicit", "source": "ruki_default"}
            }
        }
        
        # Targets (waypoints)
        self.targets = []
        self.target_counter = 0
        
        # IO Map
        self.io_map = {}
        
        # Program steps
        self.steps = []
        self.instruction_index = 0
        
        # Current state tracking - ALL ANGLES IN DEGREES
        self.current_state = {
            "active_frame": "world",
            "active_frame_id": -1,
            "active_tool": "tool0",
            "active_tool_id": -1,
            "speed_linear": 500.0,      # mm/s
            "speed_joints": 60.0,       # deg/s (NOT rad/s)
            "accel_linear": 2000.0,     # mm/s²
            "accel_joints": 180.0,      # deg/s² (NOT rad/s²)
            "rounding": 0.0,            # mm
        }
        
        # Initial state snapshot (will be set in ProgStart)
        self.initial_state = None
        
        # Subprograms
        self.subprograms = {}
        self.current_subprogram = None
    
    # ==========================================================================
    # STATE MANAGEMENT
    # ==========================================================================
    
    def _copy_state(self):
        """Create a deep copy of the current state."""
        return dict(self.current_state)
    
    def _create_meta(self, kind, source, **extra):
        """Create a _meta object for traceability."""
        meta = {
            "kind": kind,
            "source": source,
        }
        meta.update(extra)
        return meta
    
    # ==========================================================================
    # TARGET MANAGEMENT
    # ==========================================================================
    
    def _add_target(self, pose, joints, conf_RLF, name=None):
        """
        Add a target and return its ID.
        
        Parameters:
            pose: RoboDK Mat (4x4) or None - T_frame→tcp
            joints: list of joint values in DEGREES
            conf_RLF: configuration [REAR, LOWER-ARM, FLIP] or None
            name: optional target name
        
        Returns:
            target_id: string ID like "T001"
        """
        self.target_counter += 1
        target_id = f"T{self.target_counter:03d}"
        
        # Determine if this is a joint-only target
        is_joint_target = pose is None
        
        # Convert data
        joints_list = joints_to_list(joints)
        pose_xyzrpw = pose_to_xyzrpw_deg(pose)
        config_list = config_to_list(conf_RLF)
        
        target = {
            "id": target_id,
            "name": name if name else f"Target_{self.target_counter}",
            "is_joint_target": is_joint_target,
            
            # Joint data - DEGREES
            "joints": joints_list,
            "joints_unit": "deg",
            
            # Pose data - T_frame→tcp, DEGREES for rotation
            "pose": pose_xyzrpw,
            "pose_format": "xyzrpw_mm_deg",
            
            # Configuration
            "config_RLF": config_list,
            
            # Context at creation time
            "context": {
                "frame": self.current_state["active_frame"],
                "frame_id": self.current_state["active_frame_id"],
                "tool": self.current_state["active_tool"],
                "tool_id": self.current_state["active_tool_id"],
            },
            
            # External axes (if available)
            "external_axes": {
                "track_pose": pose_to_xyzrpw_deg(self._PoseTrack) if self._PoseTrack else None,
                "turntable_pose": pose_to_xyzrpw_deg(self._PoseTurntable) if self._PoseTurntable else None,
            },
        }
        
        # Include full 4x4 matrix if enabled
        if self.INCLUDE_MATRICES and pose is not None:
            target["pose_matrix"] = pose_to_matrix(pose)
        
        self.targets.append(target)
        return target_id
    
    # ==========================================================================
    # STEP MANAGEMENT
    # ==========================================================================
    
    def _add_step(self, step_type, **kwargs):
        """
        Add a program step with full state tracking.
        
        Parameters:
            step_type: Type of step (MOVE_J, MOVE_L, SET_FRAME, etc.)
            **kwargs: Step-specific data
        """
        self.instruction_index += 1
        
        step = {
            "index": self.instruction_index,
            "type": step_type,
            "state_before": self._copy_state(),
        }
        
        # Add step-specific data (excluding internal _callback)
        for key, value in kwargs.items():
            if not key.startswith('_'):
                step[key] = value
        
        # Update state based on step type
        if step_type == "SET_FRAME":
            self.current_state["active_frame"] = kwargs.get("frame", self.current_state["active_frame"])
            self.current_state["active_frame_id"] = kwargs.get("frame_id", -1)
        
        elif step_type == "SET_TOOL":
            self.current_state["active_tool"] = kwargs.get("tool", self.current_state["active_tool"])
            self.current_state["active_tool_id"] = kwargs.get("tool_id", -1)
        
        elif step_type == "SET_SPEED":
            if "speed_linear" in kwargs:
                self.current_state["speed_linear"] = kwargs["speed_linear"]
            if "speed_joints" in kwargs:
                self.current_state["speed_joints"] = kwargs["speed_joints"]
        
        elif step_type == "SET_ACCEL":
            if "accel_linear" in kwargs:
                self.current_state["accel_linear"] = kwargs["accel_linear"]
            if "accel_joints" in kwargs:
                self.current_state["accel_joints"] = kwargs["accel_joints"]
        
        elif step_type == "SET_ROUNDING":
            self.current_state["rounding"] = kwargs.get("rounding", 0)
        
        # Add state after
        step["state_after"] = self._copy_state()
        
        self.steps.append(step)
    
    # ==========================================================================
    # IO MANAGEMENT
    # ==========================================================================
    
    def _get_io_ref(self, io_var, io_type):
        """
        Get or create an IO reference.
        
        Parameters:
            io_var: IO variable (int or str)
            io_type: Type ("DO", "DI", "AO", "AI")
        
        Returns:
            io_ref: Reference name for the IO
        """
        io_ref = f"{io_type}_{io_var}"
        
        if io_ref not in self.io_map:
            self.io_map[io_ref] = {
                "type": io_type,
                "index": io_var if isinstance(io_var, int) else str(io_var),
            }
        
        return io_ref
    
    # ==========================================================================
    # ROBODK POST PROCESSOR CALLBACKS
    # ==========================================================================
    
    def ProgStart(self, progname, *args, **kwargs):
        """Start a new program."""
        self.PROG_NAME = filter_name(progname)
        self.PROG_NAMES.append(self.PROG_NAME)
        
        # Capture initial state snapshot (first program only)
        if self.initial_state is None:
            self.initial_state = self._copy_state()
        
        # Track subprograms
        if len(self.PROG_NAMES) > 1:
            self.current_subprogram = self.PROG_NAME
            self.subprograms[self.PROG_NAME] = {
                "start_step": self.instruction_index + 1,
            }
    
    def ProgFinish(self, progname, *args, **kwargs):
        """Finish the current program."""
        if self.current_subprogram:
            self.subprograms[self.current_subprogram]["end_step"] = self.instruction_index
            self.current_subprogram = None
    
    def ProgSave(self, folder, progname, ask_user=False, show_result=False, *args, **kwargs):
        """Save the program as a .ruki file."""
        
        # Build the complete IR structure
        ruki_data = {
            "schema_version": self.SCHEMA_VERSION,
            "ruki_version": self.RUKI_VERSION,
            
            "metadata": {
                "program_name": self.PROG_NAME,
                "created": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "generator": "Ruki-E (Extractor)",
                "generator_version": self.RUKI_VERSION,
                
                "source": {
                    "software": "RoboDK",
                    "post_processor": self.ROBOT_POST,
                },
                
                # IMPORTANT: All angles are in DEGREES throughout the file
                "units": {
                    "length": "mm",
                    "angle": "deg",
                    "linear_speed": "mm/s",
                    "angular_speed": "deg/s",
                    "linear_accel": "mm/s²",
                    "angular_accel": "deg/s²",
                    "time": "s",
                },
                
                # Transformation semantics
                "transform_conventions": {
                    "frame_pose": "T_world_to_frame",
                    "tool_pose": "T_flange_to_tcp",
                    "target_pose": "T_frame_to_tcp",
                    "config_RLF": "[REAR, LOWER_ARM, FLIP] where 0=front/upper/non-flip",
                },
            },
            
            "robot": {
                "name": self.ROBOT_NAME,
                "native_name": self.NATIVE_NAME,
                "axes_count": self.ROBOT_AXES,
                "axes_type": self.AXES_TYPE,
                "ip_address": self.IP_COM,
                "pulses_per_deg": self.PULSES_X_DEG,
                
                "external_axes": {
                    "turntable_offset": pose_to_xyzrpw_deg(self.POSE_TURNTABLE) if self.POSE_TURNTABLE else None,
                    "rail_offset": pose_to_xyzrpw_deg(self.POSE_RAIL) if self.POSE_RAIL else None,
                },
            },
            
            "frames": self.frames,
            "tools": self.tools,
            "targets": self.targets,
            "io_map": self.io_map,
            
            "program": {
                "main": self.PROG_NAMES[0] if self.PROG_NAMES else self.PROG_NAME,
                "subprograms": list(self.subprograms.keys()),
                "initial_state": self.initial_state if self.initial_state else self._copy_state(),
                "steps": self.steps,
            },
            
            "statistics": {
                "total_steps": len(self.steps),
                "total_targets": len(self.targets),
                "move_j_count": sum(1 for s in self.steps if s["type"] == "MOVE_J"),
                "move_l_count": sum(1 for s in self.steps if s["type"] == "MOVE_L"),
                "move_c_count": sum(1 for s in self.steps if s["type"] == "MOVE_C"),
                "io_operations": sum(1 for s in self.steps if s["type"] in ["SET_IO", "WAIT_IO"]),
                "frames_defined": len(self.frames),
                "tools_defined": len(self.tools),
            },
        }
        
        # Determine save path
        filesave = folder + '/' + self.PROG_NAME + '.' + self.PROG_EXT
        
        if ask_user:
            if robodialogs:
                filesave = robodialogs.getSaveFileName(folder, self.PROG_NAME + '.' + self.PROG_EXT)
                if not filesave:
                    return
        
        # Ensure folder exists
        os.makedirs(os.path.dirname(filesave), exist_ok=True)
        
        # Write JSON file
        with open(filesave, 'w', encoding='utf-8') as f:
            if self.PRETTY_PRINT:
                json.dump(ruki_data, f, indent=2, ensure_ascii=False)
            else:
                json.dump(ruki_data, f, ensure_ascii=False)
        
        self.PROG_FILES.append(filesave)
        print(f"Ruki IR saved: {filesave}")
        print(f"  Steps: {ruki_data['statistics']['total_steps']}")
        print(f"  Targets: {ruki_data['statistics']['total_targets']}")
        print(f"  MoveJ: {ruki_data['statistics']['move_j_count']}")
        print(f"  MoveL: {ruki_data['statistics']['move_l_count']}")
    
    def ProgSendRobot(self, robot_ip, remote_path, ftp_user, ftp_pass, *args, **kwargs):
        """Send program to robot (not applicable for Ruki-E)."""
        print("Ruki-E: ProgSendRobot not implemented (use emitters to generate robot-specific code)")
    
    # ==========================================================================
    # MOVEMENT CALLBACKS
    # ==========================================================================
    
    def MoveJ(self, pose, joints, conf_RLF, *args, **kwargs):
        """Joint movement."""
        target_name = self._TargetName
        target_id = self._add_target(pose, joints, conf_RLF, target_name)
        
        self._add_step("MOVE_J",
            target=target_id,
            target_name=target_name,
        )
        
        # Reset target name
        self._TargetName = None
    
    def MoveL(self, pose, joints, conf_RLF, *args, **kwargs):
        """Linear movement."""
        target_name = self._TargetName
        target_id = self._add_target(pose, joints, conf_RLF, target_name)
        
        self._add_step("MOVE_L",
            target=target_id,
            target_name=target_name,
        )
        
        # Reset target name
        self._TargetName = None
    
    def MoveC(self, pose1, joints1, pose2, joints2, conf_RLF_1, conf_RLF_2, *args, **kwargs):
        """Circular movement."""
        via_name = self._TargetNameVia
        end_name = self._TargetName
        
        via_id = self._add_target(pose1, joints1, conf_RLF_1, via_name)
        end_id = self._add_target(pose2, joints2, conf_RLF_2, end_name)
        
        self._add_step("MOVE_C",
            target_via=via_id,
            target_via_name=via_name,
            target_end=end_id,
            target_end_name=end_name,
        )
        
        # Reset target names
        self._TargetName = None
        self._TargetNameVia = None
    
    # ==========================================================================
    # FRAME AND TOOL CALLBACKS
    # ==========================================================================
    
    def setFrame(self, pose, frame_id, frame_name, *args, **kwargs):
        """Set reference frame. Pose is T_world→frame."""
        frame_key = filter_name(frame_name) if frame_name else f"frame_{frame_id}"
        
        # Add/update frame
        frame_data = {
            "parent": "world",
            "pose": pose_to_xyzrpw_deg(pose),
            "pose_format": "xyzrpw_mm_deg",
            "frame_id": frame_id,
            "original_name": frame_name,
        }
        
        if self.INCLUDE_MATRICES:
            frame_data["pose_matrix"] = pose_to_matrix(pose)
        
        self.frames[frame_key] = frame_data
        
        self._add_step("SET_FRAME",
            frame=frame_key,
            frame_id=frame_id,
            frame_name=frame_name,
        )
    
    def setTool(self, pose, tool_id, tool_name, *args, **kwargs):
        """Set tool (TCP). Pose is T_flange→tcp."""
        tool_key = filter_name(tool_name) if tool_name else f"tool_{tool_id}"
        
        # Add/update tool
        tool_data = {
            "tcp_pose": pose_to_xyzrpw_deg(pose),
            "pose_format": "xyzrpw_mm_deg",
            "tool_id": tool_id,
            "original_name": tool_name,
            "payload_mass": None,
            "payload_cog": None,
        }
        
        if self.INCLUDE_MATRICES:
            tool_data["pose_matrix"] = pose_to_matrix(pose)
        
        self.tools[tool_key] = tool_data
        
        self._add_step("SET_TOOL",
            tool=tool_key,
            tool_id=tool_id,
            tool_name=tool_name,
        )
    
    # ==========================================================================
    # SPEED AND ACCELERATION CALLBACKS
    # ==========================================================================
    
    def setSpeed(self, speed_mms, *args, **kwargs):
        """Set linear speed (mm/s)."""
        self._add_step("SET_SPEED",
            speed_linear=float(speed_mms),
        )
    
    def setSpeedJoints(self, speed_degs, *args, **kwargs):
        """Set joint speed (deg/s) - NO CONVERSION, stored as-is."""
        self._add_step("SET_SPEED",
            speed_joints=float(speed_degs),
        )
    
    def setAcceleration(self, accel_mmss, *args, **kwargs):
        """Set linear acceleration (mm/s²)."""
        self._add_step("SET_ACCEL",
            accel_linear=float(accel_mmss),
        )
    
    def setAccelerationJoints(self, accel_degss, *args, **kwargs):
        """Set joint acceleration (deg/s²) - NO CONVERSION, stored as-is."""
        self._add_step("SET_ACCEL",
            accel_joints=float(accel_degss),
        )
    
    def setZoneData(self, zone_mm, *args, **kwargs):
        """Set blending/rounding radius (mm)."""
        self._add_step("SET_ROUNDING",
            rounding=float(zone_mm),
        )
    
    # ==========================================================================
    # IO CALLBACKS
    # ==========================================================================
    
    def setDO(self, io_var, io_value, *args, **kwargs):
        """Set digital output."""
        io_ref = self._get_io_ref(io_var, "DO")
        
        self._add_step("SET_IO",
            io_ref=io_ref,
            io_type="DO",
            io_index=io_var,
            value=bool(io_value) if isinstance(io_value, (int, bool)) else io_value,
        )
    
    def setAO(self, io_var, io_value, *args, **kwargs):
        """Set analog output."""
        io_ref = self._get_io_ref(io_var, "AO")
        
        self._add_step("SET_IO",
            io_ref=io_ref,
            io_type="AO",
            io_index=io_var,
            value=float(io_value),
        )
    
    def waitDI(self, io_var, io_value, timeout_ms=-1, *args, **kwargs):
        """Wait for digital input."""
        io_ref = self._get_io_ref(io_var, "DI")
        
        step_data = {
            "io_ref": io_ref,
            "io_type": "DI",
            "io_index": io_var,
            "value": bool(io_value) if isinstance(io_value, (int, bool)) else io_value,
        }
        
        if timeout_ms > 0:
            step_data["timeout_s"] = timeout_ms / 1000.0
        
        self._add_step("WAIT_IO", **step_data)
    
    # ==========================================================================
    # OTHER CALLBACKS
    # ==========================================================================
    
    def Pause(self, time_ms, *args, **kwargs):
        """Pause program execution."""
        self._add_step("PAUSE",
            duration_s=time_ms / 1000.0 if time_ms > 0 else None,
            is_user_pause=time_ms < 0,
        )
    
    def RunCode(self, code, is_function_call=False, *args, **kwargs):
        """Run code or call function."""
        self._add_step("RUN_CODE",
            code=code,
            is_function_call=is_function_call,
        )
    
    def RunMessage(self, message, iscomment=False, *args, **kwargs):
        """Display message or add comment."""
        self._add_step("MESSAGE",
            text=message,
            is_comment=iscomment,
        )
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def addline(self, line):
        """Not used - Ruki-E doesn't generate text output."""
        pass
    
    def addlog(self, message):
        """Add to log."""
        self.LOG += message + '\n'
        print(f"Ruki-E LOG: {message}")


# ============================================================================
# TEST FUNCTION
# ============================================================================

def test_post():
    """Test the Ruki-E post processor with a sample program."""
    
    # Mock pose function for standalone testing
    def p(x, y, z, rx, ry, rz):
        """Mock pose - returns list instead of Mat when RoboDK not available."""
        return [x, y, z, rx, ry, rz]
    
    if ROBODK_AVAILABLE:
        try:
            from robodk.robomath import PosePP as p
        except:
            from robodk import PosePP as p
    
    print("=" * 60)
    print("Testing Ruki-E (Extractor) v1.1 Post Processor")
    print(f"RoboDK available: {ROBODK_AVAILABLE}")
    print("=" * 60)
    
    # Create post processor instance
    r = RobotPost(
        robotpost="Ruki_E",
        robotname="UR10e",
        robot_axes=6,
        axes_type=['R', 'R', 'R', 'R', 'R', 'R'],
        native_name="UR10e",
        ip_com="192.168.1.100"
    )
    
    # Start program
    r.ProgStart("TestProgram")
    
    # Add a comment
    r.RunMessage("Program generated by Ruki-E Test", True)
    
    # Set frame
    r.setFrame(p(500, 200, 0, 0, 0, 0), 1, "WorkFrame")
    
    # Set tool
    r.setTool(p(0, 0, 100, 0, 0, 0), 1, "Gripper")
    
    # Set speeds (in deg/s for joints, mm/s for linear)
    r.setSpeed(500)
    r.setSpeedJoints(60)
    r.setZoneData(5)
    
    # Move J (joints in degrees)
    r._TargetName = "Home"
    r.MoveJ(None, [0, -90, 0, -90, 0, 0], None)
    
    # IO
    r.setDO(1, 1)
    
    # Move L (pose in mm and degrees)
    r._TargetName = "Point1"
    r.MoveL(p(600, 300, 400, 180, 0, 180), [28.6, -68.8, -45.8, -57.3, 34.4, 28.6], [0, 0, 0])
    
    # Wait
    r.Pause(500)
    
    # Wait for input
    r.waitDI(0, 1, 5000)
    
    # IO
    r.setDO(1, 0)
    
    # Move J back
    r._TargetName = "Home2"
    r.MoveJ(None, [0, -90, -90, 0, 90, 0], None)
    
    # Finish
    r.ProgFinish("TestProgram")
    
    # Save
    import tempfile
    r.ProgSave(tempfile.gettempdir(), "TestProgram")
    
    # Print result
    print("\n" + "=" * 60)
    print("Test completed!")
    print(f"Output file: {r.PROG_FILES[0] if r.PROG_FILES else 'None'}")
    print("=" * 60)
    
    # Print the generated JSON (first 80 lines)
    if r.PROG_FILES:
        print("\nGenerated .ruki file content (preview):")
        print("-" * 40)
        with open(r.PROG_FILES[0], 'r') as f:
            content = f.read()
            lines = content.split('\n')
            for i, line in enumerate(lines[:80]):
                print(line)
            if len(lines) > 80:
                print(f"... ({len(lines) - 80} more lines)")


if __name__ == "__main__":
    test_post()
