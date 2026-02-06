using System;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;

public class RL_Receiver : MonoBehaviour
{
    public int porta = 20505;
    public Transform J1, J2, J3, J4, J5, J6;

    private TcpListener servidor;
    private Thread redeThread;
    private float[] angulos = new float[6];
    private bool temDados = false;

    void Start()
    {
        redeThread = new Thread(Escutar);
        redeThread.IsBackground = true;
        redeThread.Start();
    }

    void Update()
    {
        if (temDados)
        {
            // AQUI ESTÁ O SEGREDO: 
            // AngleAxis(Ângulo, Eixo Local). 
            // Se o robô ficar torto, só precisamos trocar o Vector3.up/right/forward abaixo.

            J1.localRotation = Quaternion.AngleAxis(-angulos[0], Vector3.forward);      // J1: Geralmente Up (Y)
            J2.localRotation = Quaternion.AngleAxis(-angulos[1], Vector3.up); // J2: Tente Forward ou Right
            J3.localRotation = Quaternion.AngleAxis(-angulos[2], Vector3.up);
            J4.localRotation = Quaternion.AngleAxis(-angulos[3], Vector3.up);
            J5.localRotation = Quaternion.AngleAxis(-angulos[4], Vector3.back);
            J6.localRotation = Quaternion.AngleAxis(-angulos[5], Vector3.up);

            temDados = false;
        }
    }

    private void Escutar()
    {
        servidor = new TcpListener(IPAddress.Any, porta);
        servidor.Start();
        while (true)
        {
            using (TcpClient cliente = servidor.AcceptTcpClient())
            using (StreamReader reader = new StreamReader(cliente.GetStream()))
            {
                while (!reader.EndOfStream)
                {
                    string linha = reader.ReadLine(); // Lê até o \n
                    if (!string.IsNullOrEmpty(linha))
                    {
                        string[] partes = linha.Split(',');
                        if (partes.Length >= 6)
                        {
                            for (int i = 0; i < 6; i++) angulos[i] = float.Parse(partes[i], CultureInfo.InvariantCulture);
                            temDados = true;
                        }
                    }
                }
            }
        }
    }
}