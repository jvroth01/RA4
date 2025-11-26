# Documentação das Otimizações de Código

## Autor: João Victor Roth
## PUCPR 2025 - Linguagens Formais e Compiladores

---

## 1. Constant Folding (Dobramento de Constantes)

### Descrição
O Constant Folding é uma técnica de otimização que avalia expressões envolvendo apenas constantes em tempo de compilação, substituindo-as pelo resultado calculado.

### Implementação
```python
def _constant_folding(self, tac):
    for inst in tac:
        if inst.tipo == "BINOP" and eh_numero(inst.op1) and eh_numero(inst.op2):
            resultado = avaliar(inst.op1, inst.operador, inst.op2)
            # Substitui BINOP por ASSIGN
```

### Exemplo
**Antes:**
```
t1 = 2 + 3
t2 = 4 * 5
t3 = t1 + t2
```

**Depois:**
```
t1 = 5
t2 = 20
t3 = t1 + t2
```

### Impacto
- Reduz número de operações em tempo de execução
- Especialmente útil para expressões com literais
- No Arduino, economiza ciclos de clock preciosos

---

## 2. Constant Propagation (Propagação de Constantes)

### Descrição
Substitui variáveis por seus valores constantes conhecidos, permitindo que mais expressões sejam avaliadas em tempo de compilação.

### Implementação
```python
def _constant_propagation(self, tac):
    valores = {}  # Mapa de variável -> valor constante
    
    for inst in tac:
        if inst.tipo == "ASSIGN" and eh_numero(inst.op1):
            valores[inst.destino] = inst.op1
        
        if inst.tipo == "BINOP":
            # Substitui operandos por valores conhecidos
            op1 = valores.get(inst.op1, inst.op1)
            op2 = valores.get(inst.op2, inst.op2)
```

### Exemplo
**Antes:**
```
t1 = 5
t2 = t1 + 3
t3 = t2 * 2
```

**Depois:**
```
t1 = 5
t2 = 8      ; t1 substituído por 5, depois folding: 5+3=8
t3 = 16     ; t2 substituído por 8, depois folding: 8*2=16
```

### Impacto
- Habilita mais oportunidades de constant folding
- Reduz dependências de dados
- Permite eliminação de código morto

---

## 3. Dead Code Elimination (Eliminação de Código Morto)

### Descrição
Remove instruções cujos resultados nunca são utilizados, reduzindo o tamanho do código e o tempo de execução.

### Implementação
```python
def _dead_code(self, tac):
    usados = set()
    
    # Primeira passagem: coleta variáveis usadas
    for inst in tac:
        if inst.op1 and not eh_numero(inst.op1):
            usados.add(inst.op1)
        if inst.op2 and not eh_numero(inst.op2):
            usados.add(inst.op2)
    
    # Segunda passagem: remove não usadas
    for inst in tac:
        if inst.destino not in usados:
            # Remove instrução
```

### Exemplo
**Antes:**
```
t1 = 5
t2 = 3          ; t2 nunca é usado
t3 = t1 + 2
print t3
```

**Depois:**
```
t1 = 5
t3 = t1 + 2
print t3
```

### Impacto
- Reduz tamanho do código gerado
- Menos instruções = menos ciclos de clock
- Especialmente importante em microcontroladores com memória limitada

---

## 4. Otimizações Combinadas

As três técnicas trabalham em conjunto através de múltiplas passagens:

```
Passagem 1: Constant Propagation → Constant Folding → Dead Code
Passagem 2: Constant Propagation → Constant Folding → Dead Code
Passagem 3: Constant Propagation → Constant Folding → Dead Code
```

### Exemplo Completo

**Código Original:**
```
(5 A MEM)
(3 B MEM)
(A B + C MEM)
(C 2 * D MEM)
(D)
```

**TAC Original:**
```
MEM[A] = 5
MEM[B] = 3
t0 = MEM[A]
t1 = MEM[B]
t2 = t0 + t1
MEM[C] = t2
t3 = MEM[C]
t4 = t3 * 2
MEM[D] = t4
t5 = MEM[D]
print t5
```

**TAC Otimizado:**
```
MEM[A] = 5
MEM[B] = 3
t2 = 8        ; Propagação + Folding: 5 + 3 = 8
MEM[C] = t2
t4 = 16       ; Propagação + Folding: 8 * 2 = 16
MEM[D] = t4
print 16      ; Valor final propagado
```

---

## 5. Considerações para Arduino (ATmega328P)

### Limitações
- Não otimiza loops (valores mudam a cada iteração)
- Não faz otimizações inter-procedurais
- Reset de valores conhecidos em labels (pontos de entrada de loop)

### Benefícios no Arduino
- Redução de código → economia de flash (32KB limitados)
- Menos operações → menor consumo de energia
- Execução mais rápida → melhor responsividade

---

## 6. Estatísticas Típicas

| Programa | Instruções Antes | Instruções Depois | Otimizações |
|----------|------------------|-------------------|-------------|
| teste1   | 6                | 6                 | 0           |
| fatorial | 19               | 19                | 0*          |
| fibonacci| 26               | 26                | 0*          |
| taylor   | 31               | 31                | 0*          |

*Nota: Programas com loops têm poucas otimizações porque os valores são dinâmicos

---

## 7. Código-Fonte da Otimização

```python
class OtimizadorTAC:
    def otimizar(self, tac):
        resultado = tac.copy()
        
        # 3 passagens para máxima otimização
        for _ in range(3):
            resultado = self._constant_propagation(resultado)
            resultado = self._constant_folding(resultado)
            resultado = self._dead_code(resultado)
        
        return resultado
```

---

## Referências

- Aho, Sethi, Ullman - "Compilers: Principles, Techniques, and Tools" (Dragon Book)
- Cooper, Torczon - "Engineering a Compiler"
- Muchnick - "Advanced Compiler Design and Implementation"
