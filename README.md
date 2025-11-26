# Compilador RPN - Fase 4

## Informações Acadêmicas

- **Instituição:** Pontifícia Universidade Católica do Paraná (PUCPR)
- **Ano:** 2025
- **Disciplina:** Linguagens Formais e Compiladores
- **Professor:** Frank Coelho de Alcântara

## Integrante do Grupo

- João Victor Roth - jvroth01

**Grupo no Canvas:** RA3-10

---

## Descrição do Projeto

Este projeto implementa um compilador completo para uma linguagem baseada em notação polonesa reversa (RPN), com as seguintes fases:

1. **Fase 1 - Análise Léxica:** Tokenização do código fonte
2. **Fase 2 - Análise Sintática:** Construção da AST (Árvore Sintática Abstrata)
3. **Fase 3 - Análise Semântica:** Verificação de tipos e construção da AST atribuída
4. **Fase 4 - Geração de Código:**
   - Geração de código intermediário (Three Address Code - TAC)
   - Otimização do TAC
   - Geração de código Assembly AVR para Arduino Uno
   - Integração com toolchain AVR (avr-gcc, avr-objcopy, avrdude)
   - Geração automática de arquivos .s, .elf e .hex
   - Upload automático para Arduino

### Suporte a FP16 (IEEE 754 Half Precision)

O compilador gera código Assembly AVR com suporte completo a operações em ponto flutuante de meia precisão (16 bits):

- Soma (`+`)
- Subtração (`-`)
- Multiplicação (`*`)
- Divisão real (`|`)
- Comparações (`>`, `<`, `>=`, `<=`, `==`, `!=`)

---

## Estrutura de Arquivos

```
├── compilador_fase4_fp16.py    # Compilador completo
├── fatorial.txt                # Teste: Fatorial de 8
├── fibonacci.txt               # Teste: Sequência de Fibonacci
├── taylor.txt                  # Teste: Série de Taylor para COSSENO
├── README.md                   # Este arquivo
├── OTIMIZACOES.md              # Documentação das otimizações
└── [arquivos gerados]/
    ├── *_tokens.json           # Tokens (Fase 1)
    ├── *_ast.json              # AST (Fase 2)
    ├── *_ast_atribuida.json    # AST Atribuída (Fase 3)
    ├── *_tac.txt               # TAC (Fase 4.1)
    ├── *_tac_otimizado.txt     # TAC Otimizado (Fase 4.2)
    ├── *_relatorio.md          # Relatório de otimizações
    ├── *.s                     # Assembly AVR (GNU AS)
    ├── *.elf                   # Binário ELF
    └── *.hex                   # Intel HEX para Arduino
```

---

## Instruções de Compilação e Execução

### Requisitos

- Python 3.8+
- Toolchain AVR:
  - `avr-gcc` (compilador)
  - `avr-objcopy` (extrator de HEX)
  - `avrdude` (upload para Arduino)

### Instalação da Toolchain AVR

**macOS (Homebrew):**
```bash
# Instalar Homebrew (se não tiver)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Instalar toolchain AVR
brew tap osx-cross/avr
brew install avr-gcc
brew install avrdude
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install gcc-avr avr-libc avrdude
```

### Uso do Compilador

```
python compilador_fase4_fp16.py <arquivo.txt> [opções]

OPÇÕES:
    --upload          Faz upload automático para o Arduino
    --port <porta>    Especifica porta serial manualmente
    --no-build        Apenas gera .s, não compila .elf/.hex
    --help            Mostra ajuda
```

### Exemplos

```bash
# Compilação completa (gera .s, .elf, .hex)
python compilador_fase4_fp16.py fatorial.txt

# Compilação e upload automático
python compilador_fase4_fp16.py fatorial.txt --upload

# Especificar porta serial manualmente
python compilador_fase4_fp16.py fatorial.txt --upload --port /dev/cu.usbmodem14101
```

---

## 🍎 Guia Completo para Arduino no macOS

### Passo 1: Conectar o Arduino

1. Conecte o Arduino Uno ao Mac via cabo USB
2. O Mac deve reconhecer automaticamente

### Passo 2: Descobrir a Porta Serial

Abra o Terminal e execute:
```bash
ls /dev/tty.usb*
```

Você verá algo como:
```
/dev/tty.usbmodem14101
```
ou
```
/dev/tty.usbserial-1420
```

**Anote esse caminho!**

### Passo 3: Compilar e Fazer Upload

```bash
# Opção 1: Upload automático (detecta porta)
python compilador_fase4_fp16.py fatorial.txt --upload

# Opção 2: Especificar porta manualmente
python compilador_fase4_fp16.py fatorial.txt --upload --port /dev/tty.usbmodem14101
```

### Passo 4: Ver a Saída no Serial Monitor

**Opção A - Arduino IDE:**
1. Abra o Arduino IDE
2. Vá em `Tools > Port` e selecione a porta do Arduino
3. Vá em `Tools > Serial Monitor` (ou Cmd+Shift+M)
4. Configure para **9600 baud** (canto inferior direito)

**Opção B - Terminal (screen):**
```bash
screen /dev/tty.usbmodem14101 9600
# Para sair: Ctrl+A, depois K, depois Y
```

**Opção C - Terminal (cat):**
```bash
cat /dev/tty.usbmodem14101
```

### Passo 5: Interpretar a Saída

A saída é em formato hexadecimal FP16:
- `0x0000` = 0.0
- `0x3C00` = 1.0
- `0x4000` = 2.0
- `0x4800` = 8.0
- `0x4C00` = 16.0

### Solução de Problemas

**"Porta não encontrada":**
```bash
ls /dev/tty.usb*
ls /dev/cu.usb*
```

**"avrdude: can't open device":**
- Feche o Arduino IDE e Serial Monitor
- Desconecte e reconecte o Arduino

---

## Linguagem Suportada (RPN)

```
(valor nome MEM)       ; Armazena valor em memória
(A B +)                ; Soma
(A B -)                ; Subtração
(A B *)                ; Multiplicação
(A B |)                ; Divisão real
(A B >)                ; Maior que
(A B <)                ; Menor que
(nome PRINT)           ; Imprime valor
((cond) (corpo) WHILE) ; Loop while
```

---

## Arquivos de Teste

### 1. Fatorial (fatorial.txt)
Calcula 8! = 40320

### 2. Fibonacci (fibonacci.txt)
Gera os primeiros 24 números da sequência

### 3. Série de Taylor para Cosseno (taylor.txt)
Calcula cos(0.5) ≈ 0.87758 usando:
```
cos(x) = 1 - x²/2! + x⁴/4! - x⁶/6!
```

---

## Otimizações Implementadas

1. **Constant Folding** - Avalia expressões constantes em tempo de compilação
2. **Constant Propagation** - Propaga valores constantes
3. **Dead Code Elimination** - Remove código não utilizado

Veja `OTIMIZACOES.md` para documentação completa.

---

## Convenções de Registradores AVR

| Registrador | Uso |
|-------------|-----|
| R16:R17 | Operando A (High:Low) |
| R18:R19 | Operando B (High:Low) |
| R20:R21 | Resultado (High:Low) |
| R22-R31 | Temporários |

---

## Formato FP16 (IEEE 754 Half Precision)

```
Bit:  15  14-10   9-0
      S   EEEEE   MMMMMMMMMM
    Sinal  Exp    Mantissa
```

---

## Licença

Projeto acadêmico - PUCPR 2025
