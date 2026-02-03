# Ruki — Guia de Instalação e Uso (Ruki-E + Ruki-C)

O Ruki é um sistema dividido em duas etapas:

1. Extração de informações no RoboDK
2. Compilação e geração do programa final

Essas etapas são realizadas por dois componentes:

- Ruki-E → Post-processor do RoboDK (exportação)
- Ruki-C → Aplicativo principal (compilação)

A ordem correta de uso é sempre:

RoboDK → Ruki-E → arquivos exportados → Ruki-C → programa final

---

## 1. Estrutura do Ruki

Após extrair os arquivos, você verá algo como:

Ruki.exe
assets/
postprocessor/


O arquivo importante dentro do postprocessor é:

postprocessor/Ruki_E.py


---

## 2. Instalando o Ruki-E no RoboDK

O Ruki-E precisa ser instalado dentro da pasta de post-processors do RoboDK.

### Passo a passo

1. Localize onde o RoboDK está instalado no computador
2. Dentro da pasta de instalação, procure:

Posts/


3. Copie o arquivo:

postprocessor/Ruki_E.py


para dentro de:

RoboDK/Posts/


O caminho final deve ficar assim:

RoboDK/Posts/Ruki_E.py


---

## 3. Selecionando o Ruki-E no RoboDK

Depois de copiar o arquivo:

1. No RoboDK, clique com o botão direito no seu programa
2. Selecione:

Select Post Processor

3. Na lista, escolha:

Ruki_E

Isso garante que a exportação será feita usando o Ruki-E.

---

## 4. Configurações obrigatórias no RoboDK

Para exportação correta de programas com subprogramas e chamadas internas:

1. Vá em:

Tools → Options

2. Abra a aba:

Program

3. Ative as opções:

- Inline programs
- Export targets names

Essas opções são essenciais para que subprogramas não sejam exportados apenas como comentários.

---

## 5. Tool obrigatória no programa (mesmo que fictícia)

Alguns controladores exigem que o programa tenha uma ferramenta declarada.

Mesmo que você esteja programando sem ferramenta real, faça o seguinte:

### Criar Tool no RoboDK

1. Clique com o botão direito no robô (na árvore do RoboDK)
2. Selecione:

Add Tool

### Declarar Tool no programa

No seu programa, garanta que exista uma instrução:

Set Tool

Isso é necessário porque alguns formatos não conseguem interpretar movimentos sem referência de ferramenta.

---

## 6. Usando o Ruki-C (compilação)

Após exportar o programa pelo RoboDK usando o Ruki-E:

1. Abra o aplicativo:

Ruki.exe


2. Use o Ruki-C para compilar os arquivos exportados e gerar o programa final.

---

## Checklist rápido (antes de compilar)

- [ ] Copiou `Ruki_E.py` para `RoboDK/Posts/`
- [ ] Selecionou `Ruki_E` como post-processor no programa
- [ ] Ativou Inline programs
- [ ] Ativou Export targets names
- [ ] Criou uma Tool no robô
- [ ] O programa contém um comando Set Tool
- [ ] Exportou via RoboDK e compilou no Ruki-C

---

Seguindo esses passos, o fluxo funciona corretamente:
extração limpa no RoboDK e compilação correta no Ruki-C.