#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
================================================================================
COMPILADOR RPN - FASE 4 COMPLETA COM SUPORTE FP16
Geração de Código Intermediário (TAC), Otimização e Assembly AVR

Instituição: Pontifícia Universidade Católica do Paraná (PUCPR)
Ano: 2025
Disciplina: Linguagens Formais e Compiladores
Professor: Frank Coelho de Alcântara

Integrante do grupo:
- João Victor Roth - jvroth01

Nome do grupo no Canvas: RA3-10

Fase 4: Geração de código TAC, otimização e Assembly AVR para Arduino Uno
        COM SUPORTE COMPLETO A FP16 (Half Precision - 16 bits IEEE 754)
================================================================================
"""

import sys
import json
import os
import subprocess
import glob
import platform
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple, Set
from datetime import datetime


# ============================================================================
# UTILITÁRIOS FP16 (Half Precision IEEE 754)
# ============================================================================

class FP16Converter:
    """Conversor para formato FP16 (IEEE 754 Half Precision)."""
    
    BIAS = 15
    
    @staticmethod
    def float_to_fp16(value: float) -> Tuple[int, int]:
        """Converte float Python para FP16 (byte_high, byte_low)."""
        if value == 0.0:
            return (0x00, 0x00)
        
        sign = 0
        if value < 0:
            sign = 1
            value = -value
        
        # Calcula expoente
        if value >= 1.0:
            exp = 0
            temp = value
            while temp >= 2.0:
                temp /= 2.0
                exp += 1
        else:
            exp = 0
            temp = value
            while temp < 1.0:
                temp *= 2.0
                exp -= 1
        
        biased_exp = exp + FP16Converter.BIAS
        
        if biased_exp < 0:
            biased_exp = 0
            temp = 0
        elif biased_exp > 31:
            biased_exp = 31
            temp = 1.0
        
        mantissa_float = temp - 1.0
        mantissa = int(mantissa_float * 1024)
        if mantissa > 1023:
            mantissa = 1023
        
        byte_high = (sign << 7) | (biased_exp << 2) | ((mantissa >> 8) & 0x03)
        byte_low = mantissa & 0xFF
        
        return (byte_high, byte_low)
    
    @staticmethod
    def fp16_to_float(byte_high: int, byte_low: int) -> float:
        """Converte FP16 para float Python."""
        sign = (byte_high >> 7) & 0x01
        exp = (byte_high >> 2) & 0x1F
        mantissa = ((byte_high & 0x03) << 8) | byte_low
        
        if exp == 0 and mantissa == 0:
            return 0.0
        
        mantissa_float = 1.0 + (mantissa / 1024.0)
        real_exp = exp - FP16Converter.BIAS
        value = mantissa_float * (2.0 ** real_exp)
        
        if sign:
            value = -value
        
        return value


# ============================================================================
# DEFINIÇÕES DE TIPOS E TOKENS
# ============================================================================

class TokenType(Enum):
    """Tipos de tokens reconhecidos."""
    INT_LITERAL = "INT_LITERAL"
    REAL_LITERAL = "REAL_LITERAL"
    PLUS = "PLUS"           # +
    MINUS = "MINUS"         # -
    MULT = "MULT"           # *
    DIV_REAL = "DIV_REAL"   # |
    DIV_INT = "DIV_INT"     # /
    MOD = "MOD"             # %
    POW = "POW"             # ^
    GT = "GT"               # >
    LT = "LT"               # <
    GTE = "GTE"             # >=
    LTE = "LTE"             # <=
    EQ = "EQ"               # ==
    NEQ = "NEQ"             # !=
    MEM = "MEM"
    RES = "RES"
    PRINT = "PRINT"
    IF = "IF"
    WHILE = "WHILE"
    FOR = "FOR"
    ID = "ID"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EOF = "EOF"


@dataclass
class Token:
    """Representa um token."""
    tipo: TokenType
    valor: Any
    linha: int
    coluna: int
    
    def para_dict(self) -> Dict[str, Any]:
        return {
            "tipo": self.tipo.name,
            "valor": self.valor,
            "linha": self.linha,
            "coluna": self.coluna
        }


# ============================================================================
# NÓ DA AST
# ============================================================================

@dataclass
class NoAST:
    """Nó da Árvore Sintática Abstrata."""
    tipo: str
    valor: Any = None
    tipo_dado: str = "real"
    filhos: List['NoAST'] = None
    operador: str = ""
    linha: int = 0
    
    def __post_init__(self):
        if self.filhos is None:
            self.filhos = []
    
    def para_dict(self) -> Dict[str, Any]:
        return {
            "tipo": self.tipo,
            "valor": self.valor,
            "tipo_dado": self.tipo_dado,
            "operador": self.operador,
            "filhos": [f.para_dict() for f in self.filhos]
        }
    
    def __repr__(self):
        if self.valor is not None:
            return f"NoAST({self.tipo}, {self.valor})"
        elif self.operador:
            return f"NoAST({self.tipo}, op={self.operador})"
        else:
            return f"NoAST({self.tipo}, filhos={len(self.filhos)})"


# ============================================================================
# FASE 1: ANALISADOR LÉXICO
# ============================================================================

class AnalisadorLexico:
    """Analisador Léxico (Tokenizer)."""
    
    def __init__(self, codigo: str, linha_base: int = 1):
        self.codigo = codigo
        self.pos = 0
        self.linha = linha_base
        self.coluna = 1
    
    def char_atual(self) -> Optional[str]:
        if self.pos >= len(self.codigo):
            return None
        return self.codigo[self.pos]
    
    def avancar(self) -> Optional[str]:
        if self.pos >= len(self.codigo):
            return None
        char = self.codigo[self.pos]
        self.pos += 1
        if char == '\n':
            self.linha += 1
            self.coluna = 1
        else:
            self.coluna += 1
        return char
    
    def pular_espacos(self):
        while self.char_atual() and self.char_atual() in ' \t\r\n':
            self.avancar()
    
    def pular_comentario(self) -> bool:
        if self.pos + 1 < len(self.codigo) and self.codigo[self.pos:self.pos+2] == '//':
            while self.char_atual() and self.char_atual() != '\n':
                self.avancar()
            return True
        return False
    
    def ler_numero(self) -> Token:
        col_ini = self.coluna
        num_str = ""
        tem_ponto = False
        
        while self.char_atual() and (self.char_atual().isdigit() or self.char_atual() == '.'):
            if self.char_atual() == '.':
                if tem_ponto:
                    break
                tem_ponto = True
            num_str += self.avancar()
        
        if tem_ponto:
            return Token(TokenType.REAL_LITERAL, float(num_str), self.linha, col_ini)
        else:
            return Token(TokenType.INT_LITERAL, int(num_str), self.linha, col_ini)
    
    def ler_identificador(self) -> Token:
        col_ini = self.coluna
        id_str = ""
        
        while self.char_atual() and (self.char_atual().isalnum() or self.char_atual() == '_'):
            id_str += self.avancar()
        
        # Palavras reservadas
        palavras = {
            'MEM': TokenType.MEM,
            'RES': TokenType.RES,
            'PRINT': TokenType.PRINT,
            'IF': TokenType.IF,
            'WHILE': TokenType.WHILE,
            'FOR': TokenType.FOR
        }
        
        tipo = palavras.get(id_str.upper(), TokenType.ID)
        return Token(tipo, id_str, self.linha, col_ini)
    
    def proximo_token(self) -> Token:
        self.pular_espacos()
        while self.pular_comentario():
            self.pular_espacos()
        
        if self.char_atual() is None:
            return Token(TokenType.EOF, None, self.linha, self.coluna)
        
        char = self.char_atual()
        col_ini = self.coluna
        
        if char.isdigit():
            return self.ler_numero()
        
        if char.isalpha() or char == '_':
            return self.ler_identificador()
        
        self.avancar()
        
        # Operadores de 2 caracteres
        if self.char_atual():
            dois = char + self.char_atual()
            ops_duplos = {'>=': TokenType.GTE, '<=': TokenType.LTE,
                          '==': TokenType.EQ, '!=': TokenType.NEQ}
            if dois in ops_duplos:
                self.avancar()
                return Token(ops_duplos[dois], dois, self.linha, col_ini)
        
        # Operadores simples
        ops = {'+': TokenType.PLUS, '-': TokenType.MINUS, '*': TokenType.MULT,
               '|': TokenType.DIV_REAL, '/': TokenType.DIV_INT, '%': TokenType.MOD,
               '^': TokenType.POW, '>': TokenType.GT, '<': TokenType.LT,
               '(': TokenType.LPAREN, ')': TokenType.RPAREN}
        
        if char in ops:
            return Token(ops[char], char, self.linha, col_ini)
        
        return Token(TokenType.EOF, None, self.linha, col_ini)
    
    def tokenizar(self) -> List[Token]:
        tokens = []
        while True:
            token = self.proximo_token()
            tokens.append(token)
            if token.tipo == TokenType.EOF:
                break
        return tokens


# ============================================================================
# FASE 2: PARSER RPN
# ============================================================================

class ParserRPN:
    """Parser para expressões RPN."""
    
    OPERADORES = {'+', '-', '*', '|', '/', '%', '^', '>', '<', '>=', '<=', '==', '!='}
    
    def __init__(self, tokens: List[Token], tabela_simbolos: Dict):
        self.tokens = tokens
        self.pos = 0
        self.tabela = tabela_simbolos
        self.erros = []
    
    def token_atual(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return Token(TokenType.EOF, None, 0, 0)
    
    def avancar(self) -> Token:
        token = self.token_atual()
        self.pos += 1
        return token
    
    def parse(self) -> Tuple[Optional[NoAST], List[str]]:
        """Parse principal."""
        resultado = self._parse_expressao()
        return resultado, self.erros
    
    def _parse_expressao(self) -> Optional[NoAST]:
        """Parse de uma expressão."""
        token = self.token_atual()
        
        if token.tipo == TokenType.EOF:
            return None
        
        if token.tipo == TokenType.LPAREN:
            return self._parse_grupo()
        
        if token.tipo == TokenType.INT_LITERAL:
            self.avancar()
            return NoAST("LITERAL", valor=token.valor, tipo_dado="int", linha=token.linha)
        
        if token.tipo == TokenType.REAL_LITERAL:
            self.avancar()
            return NoAST("LITERAL", valor=token.valor, tipo_dado="real", linha=token.linha)
        
        if token.tipo == TokenType.ID:
            self.avancar()
            tipo = self.tabela.get(token.valor, {}).get('tipo', 'real')
            return NoAST("ID", valor=token.valor, tipo_dado=tipo, linha=token.linha)
        
        return None
    
    def _parse_grupo(self) -> Optional[NoAST]:
        """Parse de um grupo entre parênteses."""
        if self.token_atual().tipo != TokenType.LPAREN:
            return self._parse_expressao()
        
        self.avancar()  # Consome '('
        linha = self.token_atual().linha
        
        elementos = []
        while self.token_atual().tipo not in [TokenType.RPAREN, TokenType.EOF]:
            elem = self._parse_elemento()
            if elem is not None:
                elementos.append(elem)
        
        if self.token_atual().tipo == TokenType.RPAREN:
            self.avancar()  # Consome ')'
        
        if not elementos:
            return None
        
        ultimo = elementos[-1]
        
        # ===== WHILE =====
        if isinstance(ultimo, str) and ultimo == "WHILE":
            if len(elementos) >= 3:
                condicao = elementos[0]
                corpo_elementos = elementos[1:-1]
                
                if len(corpo_elementos) == 1:
                    corpo = corpo_elementos
                else:
                    nos = [e for e in corpo_elementos if isinstance(e, NoAST)]
                    if nos:
                        corpo = [NoAST("BLOCO", tipo_dado="void", filhos=nos, linha=linha)]
                    else:
                        corpo = corpo_elementos
                
                return NoAST(
                    "WHILE",
                    tipo_dado="void",
                    filhos=[condicao] + corpo,
                    linha=linha
                )
        
        # ===== IF =====
        if isinstance(ultimo, str) and ultimo == "IF":
            if len(elementos) >= 4:
                condicao = elementos[0]
                then_bloco = elementos[1]
                else_bloco = elementos[2]
                return NoAST(
                    "IF",
                    tipo_dado="void",
                    filhos=[condicao, then_bloco, else_bloco],
                    linha=linha
                )
        
        # ===== MÚLTIPLOS COMANDOS MEM =====
        comandos = self._tentar_extrair_comandos(elementos, linha)
        if comandos:
            if len(comandos) == 1:
                return comandos[0]
            return NoAST("BLOCO", tipo_dado="void", filhos=comandos, linha=linha)
        
        # ===== MEM =====
        if isinstance(ultimo, str) and ultimo == "MEM":
            if len(elementos) >= 3:
                valor = elementos[0]
                nome_elem = elementos[1]
                nome = nome_elem.valor if isinstance(nome_elem, NoAST) else str(nome_elem)
                
                tipo_val = valor.tipo_dado if isinstance(valor, NoAST) else "real"
                self.tabela[nome] = {'tipo': tipo_val, 'linha': linha}
                
                return NoAST(
                    "MEM",
                    valor=nome,
                    tipo_dado=tipo_val,
                    filhos=[valor] if isinstance(valor, NoAST) else [],
                    linha=linha
                )
        
        # ===== PRINT =====
        if isinstance(ultimo, str) and ultimo == "PRINT":
            if len(elementos) >= 2:
                valor = elementos[0]
                return NoAST(
                    "PRINT",
                    tipo_dado="void",
                    filhos=[valor] if isinstance(valor, NoAST) else [],
                    valor=valor.valor if isinstance(valor, NoAST) else valor,
                    linha=linha
                )
        
        # ===== RES =====
        if isinstance(ultimo, str) and ultimo == "RES":
            indice = 1
            if len(elementos) >= 2 and isinstance(elementos[0], NoAST):
                if elementos[0].tipo == "LITERAL":
                    indice = elementos[0].valor
            return NoAST("RES", valor=indice, tipo_dado="real", linha=linha)
        
        # ===== OPERAÇÃO BINÁRIA =====
        if isinstance(ultimo, str) and ultimo in self.OPERADORES:
            if len(elementos) >= 3:
                op1 = elementos[0]
                op2 = elementos[1]
                operador = ultimo
                
                tipo1 = op1.tipo_dado if isinstance(op1, NoAST) else "real"
                tipo2 = op2.tipo_dado if isinstance(op2, NoAST) else "real"
                
                if operador in ['>', '<', '>=', '<=', '==', '!=']:
                    tipo_res = "bool"
                elif operador == '|':
                    tipo_res = "real"
                elif operador in ['/', '%']:
                    tipo_res = "int"
                elif tipo1 == "real" or tipo2 == "real":
                    tipo_res = "real"
                else:
                    tipo_res = "int"
                
                return NoAST(
                    "BINOP",
                    tipo_dado=tipo_res,
                    operador=operador,
                    filhos=[op1, op2] if isinstance(op1, NoAST) and isinstance(op2, NoAST) else [],
                    linha=linha
                )
        
        # ===== BLOCO =====
        if len(elementos) > 1:
            nos = [e for e in elementos if isinstance(e, NoAST)]
            if nos:
                return NoAST("BLOCO", tipo_dado="void", filhos=nos, linha=linha)
        
        if len(elementos) == 1 and isinstance(elementos[0], NoAST):
            return elementos[0]
        
        return None
    
    def _tentar_extrair_comandos(self, elementos: List, linha: int) -> List[NoAST]:
        """Extrai sequência de comandos MEM e PRINT."""
        tem_mem = any(isinstance(e, str) and e == "MEM" for e in elementos)
        if not tem_mem:
            return []
        
        comandos = []
        i = 0
        
        while i < len(elementos):
            if i + 2 < len(elementos):
                elem0 = elementos[i]
                elem1 = elementos[i + 1]
                elem2 = elementos[i + 2]
                
                if (isinstance(elem0, NoAST) and 
                    isinstance(elem1, NoAST) and elem1.tipo == "ID" and
                    isinstance(elem2, str) and elem2 == "MEM"):
                    
                    nome = elem1.valor
                    tipo_val = elem0.tipo_dado
                    self.tabela[nome] = {'tipo': tipo_val, 'linha': linha}
                    
                    comandos.append(NoAST(
                        "MEM",
                        valor=nome,
                        tipo_dado=tipo_val,
                        filhos=[elem0],
                        linha=linha
                    ))
                    i += 3
                    continue
            
            if i + 1 < len(elementos):
                elem0 = elementos[i]
                elem1 = elementos[i + 1]
                
                if isinstance(elem0, NoAST) and isinstance(elem1, str) and elem1 == "PRINT":
                    comandos.append(NoAST(
                        "PRINT",
                        tipo_dado="void",
                        filhos=[elem0],
                        valor=elem0.valor if elem0.tipo == "ID" else None,
                        linha=linha
                    ))
                    i += 2
                    continue
            
            if isinstance(elementos[i], NoAST):
                proximo_e_keyword = (i + 1 < len(elementos) and 
                                     isinstance(elementos[i + 1], str) and 
                                     elementos[i + 1] in ["MEM", "PRINT"])
                if not proximo_e_keyword:
                    comandos.append(elementos[i])
            
            i += 1
        
        return comandos
    
    def _parse_elemento(self) -> Any:
        """Parse de um elemento individual."""
        token = self.token_atual()
        
        if token.tipo in [TokenType.EOF, TokenType.RPAREN]:
            return None
        
        if token.tipo == TokenType.LPAREN:
            return self._parse_grupo()
        
        if token.tipo == TokenType.INT_LITERAL:
            self.avancar()
            return NoAST("LITERAL", valor=token.valor, tipo_dado="int", linha=token.linha)
        
        if token.tipo == TokenType.REAL_LITERAL:
            self.avancar()
            return NoAST("LITERAL", valor=token.valor, tipo_dado="real", linha=token.linha)
        
        if token.tipo == TokenType.ID:
            self.avancar()
            tipo = self.tabela.get(token.valor, {}).get('tipo', 'real')
            return NoAST("ID", valor=token.valor, tipo_dado=tipo, linha=token.linha)
        
        if token.tipo in [TokenType.PLUS, TokenType.MINUS, TokenType.MULT,
                          TokenType.DIV_REAL, TokenType.DIV_INT, TokenType.MOD,
                          TokenType.POW, TokenType.GT, TokenType.LT,
                          TokenType.GTE, TokenType.LTE, TokenType.EQ, TokenType.NEQ]:
            self.avancar()
            return token.valor
        
        if token.tipo in [TokenType.MEM, TokenType.RES, TokenType.PRINT,
                          TokenType.IF, TokenType.WHILE, TokenType.FOR]:
            self.avancar()
            return token.tipo.name
        
        self.avancar()
        return None


# ============================================================================
# INSTRUÇÕES TAC
# ============================================================================

@dataclass
class InstrucaoTAC:
    """Instrução Three Address Code."""
    tipo: str
    destino: str = None
    op1: str = None
    operador: str = None
    op2: str = None
    label: str = None
    comentario: str = ""
    
    def __str__(self):
        if self.tipo == "LABEL":
            return f"{self.label}:"
        elif self.tipo == "ASSIGN":
            return f"    {self.destino} = {self.op1}"
        elif self.tipo == "BINOP":
            return f"    {self.destino} = {self.op1} {self.operador} {self.op2}"
        elif self.tipo == "LOAD":
            return f"    {self.destino} = MEM[{self.op1}]"
        elif self.tipo == "STORE":
            return f"    MEM[{self.op1}] = {self.op2}"
        elif self.tipo == "GOTO":
            return f"    goto {self.label}"
        elif self.tipo == "IFFALSE":
            return f"    ifFalse {self.op1} goto {self.label}"
        elif self.tipo == "PRINT":
            return f"    print {self.op1}"
        elif self.tipo == "COMMENT":
            return f"; {self.comentario}"
        else:
            return f"    ; ??? {self.tipo}"


# ============================================================================
# FASE 4.1: GERADOR DE TAC
# ============================================================================

class GeradorTAC:
    """Gerador de Three Address Code."""
    
    def __init__(self):
        self.instrucoes: List[InstrucaoTAC] = []
        self.temp_count = 0
        self.label_count = 0
        self.tabela = {}
    
    def novo_temp(self) -> str:
        temp = f"t{self.temp_count}"
        self.temp_count += 1
        return temp
    
    def novo_label(self, prefixo: str = "L") -> str:
        label = f"{prefixo}{self.label_count}"
        self.label_count += 1
        return label
    
    def gerar(self, arvore: NoAST) -> List[InstrucaoTAC]:
        """Gera TAC a partir da AST."""
        self.instrucoes = []
        
        if arvore is None:
            return self.instrucoes
        
        resultado = self._processar(arvore)
        
        if resultado and arvore.tipo not in ["WHILE", "IF", "FOR", "MEM", "BLOCO", "PRINT"]:
            self.instrucoes.append(InstrucaoTAC("PRINT", op1=resultado))
        
        return self.instrucoes
    
    def _processar(self, no: NoAST) -> Optional[str]:
        """Processa um nó da AST."""
        if no is None:
            return None
        
        if no.tipo == "LITERAL":
            return str(no.valor)
        
        if no.tipo == "ID":
            temp = self.novo_temp()
            self.instrucoes.append(
                InstrucaoTAC("LOAD", destino=temp, op1=no.valor)
            )
            return temp
        
        if no.tipo == "BINOP":
            return self._processar_binop(no)
        
        if no.tipo == "MEM":
            return self._processar_mem(no)
        
        if no.tipo == "PRINT":
            return self._processar_print(no)
        
        if no.tipo == "WHILE":
            return self._processar_while(no)
        
        if no.tipo == "IF":
            return self._processar_if(no)
        
        if no.tipo == "BLOCO":
            return self._processar_bloco(no)
        
        if no.tipo == "RES":
            temp = self.novo_temp()
            self.instrucoes.append(
                InstrucaoTAC("ASSIGN", destino=temp, op1="0")
            )
            return temp
        
        resultado = None
        for filho in no.filhos:
            resultado = self._processar(filho)
        return resultado
    
    def _processar_binop(self, no: NoAST) -> str:
        """Processa operação binária."""
        if len(no.filhos) < 2:
            temp = self.novo_temp()
            self.instrucoes.append(
                InstrucaoTAC("ASSIGN", destino=temp, op1="0")
            )
            return temp
        
        op1 = self._processar(no.filhos[0])
        op2 = self._processar(no.filhos[1])
        
        temp = self.novo_temp()
        self.instrucoes.append(
            InstrucaoTAC("BINOP", destino=temp, op1=op1, 
                        operador=no.operador, op2=op2)
        )
        return temp
    
    def _processar_mem(self, no: NoAST) -> str:
        """Processa comando MEM."""
        nome = no.valor
        
        if no.filhos:
            valor = self._processar(no.filhos[0])
        else:
            valor = "0"
        
        self.instrucoes.append(
            InstrucaoTAC("STORE", op1=nome, op2=valor)
        )
        
        self.tabela[nome] = {'tipo': no.tipo_dado}
        return valor
    
    def _processar_print(self, no: NoAST) -> str:
        """Processa comando PRINT."""
        if no.filhos:
            valor = self._processar(no.filhos[0])
        elif no.valor:
            temp = self.novo_temp()
            self.instrucoes.append(
                InstrucaoTAC("LOAD", destino=temp, op1=no.valor)
            )
            valor = temp
        else:
            valor = "0"
        
        self.instrucoes.append(
            InstrucaoTAC("PRINT", op1=valor)
        )
        return valor
    
    def _processar_bloco(self, no: NoAST) -> Optional[str]:
        """Processa bloco de comandos."""
        resultado = None
        for filho in no.filhos:
            resultado = self._processar(filho)
        return resultado
    
    def _processar_while(self, no: NoAST) -> str:
        """Processa WHILE."""
        if len(no.filhos) < 2:
            return None
        
        condicao = no.filhos[0]
        corpo = no.filhos[1:]
        
        label_inicio = self.novo_label("WHILE_INICIO")
        label_fim = self.novo_label("WHILE_FIM")
        
        self.instrucoes.append(
            InstrucaoTAC("COMMENT", comentario="=== INÍCIO WHILE ===")
        )
        
        self.instrucoes.append(InstrucaoTAC("LABEL", label=label_inicio))
        
        self.instrucoes.append(
            InstrucaoTAC("COMMENT", comentario="--- Condição ---")
        )
        t_cond = self._processar(condicao)
        
        self.instrucoes.append(
            InstrucaoTAC("IFFALSE", op1=t_cond, label=label_fim)
        )
        
        self.instrucoes.append(
            InstrucaoTAC("COMMENT", comentario="--- Corpo ---")
        )
        for cmd in corpo:
            self._processar(cmd)
        
        self.instrucoes.append(
            InstrucaoTAC("GOTO", label=label_inicio)
        )
        
        self.instrucoes.append(InstrucaoTAC("LABEL", label=label_fim))
        
        self.instrucoes.append(
            InstrucaoTAC("COMMENT", comentario="=== FIM WHILE ===")
        )
        
        return None
    
    def _processar_if(self, no: NoAST) -> str:
        """Processa IF."""
        if len(no.filhos) < 3:
            return None
        
        condicao = no.filhos[0]
        then_bloco = no.filhos[1]
        else_bloco = no.filhos[2]
        
        label_else = self.novo_label("IF_ELSE")
        label_fim = self.novo_label("IF_FIM")
        
        self.instrucoes.append(
            InstrucaoTAC("COMMENT", comentario="=== IF ===")
        )
        
        t_cond = self._processar(condicao)
        
        self.instrucoes.append(
            InstrucaoTAC("IFFALSE", op1=t_cond, label=label_else)
        )
        
        self._processar(then_bloco)
        
        self.instrucoes.append(InstrucaoTAC("GOTO", label=label_fim))
        
        self.instrucoes.append(InstrucaoTAC("LABEL", label=label_else))
        self._processar(else_bloco)
        
        self.instrucoes.append(InstrucaoTAC("LABEL", label=label_fim))
        
        self.instrucoes.append(
            InstrucaoTAC("COMMENT", comentario="=== FIM IF ===")
        )
        
        return None


# ============================================================================
# FASE 4.2: OTIMIZADOR DE TAC
# ============================================================================

class OtimizadorTAC:
    """Otimizador de TAC."""
    
    def __init__(self):
        self.stats = {
            'constant_folding': 0,
            'constant_propagation': 0,
            'dead_code': 0,
            'jump_optimization': 0,
            'antes': 0,
            'depois': 0
        }
    
    def otimizar(self, tac: List[InstrucaoTAC]) -> List[InstrucaoTAC]:
        """Aplica otimizações."""
        self.stats['antes'] = len([i for i in tac if i.tipo not in ["COMMENT", "LABEL"]])
        
        resultado = [self._copiar(i) for i in tac]
        
        for _ in range(3):
            resultado = self._constant_propagation(resultado)
            resultado = self._constant_folding(resultado)
            resultado = self._dead_code(resultado)
        
        self.stats['depois'] = len([i for i in resultado if i.tipo not in ["COMMENT", "LABEL"]])
        
        return resultado
    
    def _copiar(self, inst: InstrucaoTAC) -> InstrucaoTAC:
        return InstrucaoTAC(
            tipo=inst.tipo, destino=inst.destino, op1=inst.op1,
            operador=inst.operador, op2=inst.op2, label=inst.label,
            comentario=inst.comentario
        )
    
    def _eh_numero(self, val: str) -> bool:
        if val is None:
            return False
        try:
            float(val)
            return True
        except:
            return False
    
    def _constant_folding(self, tac: List[InstrucaoTAC]) -> List[InstrucaoTAC]:
        """Avalia expressões constantes."""
        resultado = []
        
        for inst in tac:
            if inst.tipo == "BINOP" and self._eh_numero(inst.op1) and self._eh_numero(inst.op2):
                v1, v2 = float(inst.op1), float(inst.op2)
                res = None
                
                try:
                    if inst.operador == '+': res = v1 + v2
                    elif inst.operador == '-': res = v1 - v2
                    elif inst.operador == '*': res = v1 * v2
                    elif inst.operador == '/' and v2 != 0: res = int(v1 / v2)
                    elif inst.operador == '|' and v2 != 0: res = v1 / v2
                    elif inst.operador == '%' and v2 != 0: res = int(v1) % int(v2)
                    elif inst.operador == '^': res = v1 ** v2
                    elif inst.operador == '>': res = 1 if v1 > v2 else 0
                    elif inst.operador == '<': res = 1 if v1 < v2 else 0
                    elif inst.operador == '>=': res = 1 if v1 >= v2 else 0
                    elif inst.operador == '<=': res = 1 if v1 <= v2 else 0
                    elif inst.operador == '==': res = 1 if v1 == v2 else 0
                    elif inst.operador == '!=': res = 1 if v1 != v2 else 0
                except:
                    pass
                
                if res is not None:
                    res_str = str(int(res)) if res == int(res) else str(res)
                    resultado.append(InstrucaoTAC(
                        "ASSIGN", destino=inst.destino, op1=res_str
                    ))
                    self.stats['constant_folding'] += 1
                    continue
            
            resultado.append(inst)
        
        return resultado
    
    def _constant_propagation(self, tac: List[InstrucaoTAC]) -> List[InstrucaoTAC]:
        """Propaga constantes."""
        valores = {}
        resultado = []
        
        for inst in tac:
            if inst.tipo == "LABEL":
                valores.clear()
            
            if inst.tipo == "ASSIGN" and self._eh_numero(inst.op1):
                valores[inst.destino] = inst.op1
            
            if inst.tipo == "BINOP":
                op1 = valores.get(inst.op1, inst.op1)
                op2 = valores.get(inst.op2, inst.op2)
                
                if op1 != inst.op1 or op2 != inst.op2:
                    resultado.append(InstrucaoTAC(
                        "BINOP", destino=inst.destino, op1=op1,
                        operador=inst.operador, op2=op2
                    ))
                    self.stats['constant_propagation'] += 1
                    continue
            
            resultado.append(inst)
        
        return resultado
    
    def _dead_code(self, tac: List[InstrucaoTAC]) -> List[InstrucaoTAC]:
        """Remove código morto."""
        usados: Set[str] = set()
        
        for inst in tac:
            if inst.tipo == "BINOP":
                if inst.op1 and not self._eh_numero(inst.op1):
                    usados.add(inst.op1)
                if inst.op2 and not self._eh_numero(inst.op2):
                    usados.add(inst.op2)
            elif inst.tipo == "ASSIGN":
                if inst.op1 and not self._eh_numero(inst.op1):
                    usados.add(inst.op1)
            elif inst.tipo in ["PRINT", "STORE", "IFFALSE"]:
                if inst.op1 and not self._eh_numero(inst.op1):
                    usados.add(inst.op1)
                if inst.op2 and not self._eh_numero(inst.op2):
                    usados.add(inst.op2)
        
        resultado = []
        for inst in tac:
            if inst.tipo in ["ASSIGN", "BINOP", "LOAD"] and inst.destino:
                if inst.destino.startswith('t') and inst.destino not in usados:
                    self.stats['dead_code'] += 1
                    continue
            resultado.append(inst)
        
        return resultado
    
    def gerar_relatorio(self) -> str:
        """Gera relatório em Markdown."""
        total = sum([self.stats['constant_folding'], self.stats['constant_propagation'],
                     self.stats['dead_code'], self.stats['jump_optimization']])
        
        return f"""# Relatório de Otimizações

**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

## Estatísticas

| Métrica | Valor |
|---------|-------|
| Instruções antes | {self.stats['antes']} |
| Instruções depois | {self.stats['depois']} |
| Constant Folding | {self.stats['constant_folding']} |
| Constant Propagation | {self.stats['constant_propagation']} |
| Dead Code Elimination | {self.stats['dead_code']} |
| **Total de otimizações** | **{total}** |
"""


# ============================================================================
# FASE 4.3: GERADOR ASSEMBLY AVR COM FP16 COMPLETO
# ============================================================================

class GeradorAssembly:
    """
    Gerador de Assembly AVR para Arduino Uno com suporte completo a FP16.
    
    Convenções de Registradores:
    - R0-R1: Resultado de MUL (R1 deve ser limpo após uso)
    - R2-R5: Salvos para uso temporário em operações complexas
    - R16-R17: Operando A (High:Low) para operações FP16
    - R18-R19: Operando B (High:Low) para operações FP16
    - R20-R21: Resultado (High:Low) das operações FP16
    - R22-R23: Expoentes / temporários
    - R24-R25: Temporários para cálculos
    - R26-R29: Mantissas e temporários
    - R30-R31 (Z): Ponteiro para tabelas / sinal
    
    Endereçamento de memória:
    - Inicia em 0x0200 para evitar conflito com registradores Serial
    """
    
    ENDERECO_BASE = 0x0200  # Início da SRAM segura
    
    def __init__(self):
        self.asm = []
        self.variaveis = {}
        self.prox_end = self.ENDERECO_BASE
        self.label_count = 0
        self.converter = FP16Converter()
    
    def gerar(self, tac: List[InstrucaoTAC]) -> List[str]:
        """Gera código Assembly."""
        self.asm = []
        self.variaveis = {}
        self.prox_end = self.ENDERECO_BASE
        
        self._cabecalho()
        
        for inst in tac:
            if inst.tipo != "COMMENT":
                self._processar(inst)
            else:
                self.asm.append(f"    ; {inst.comentario}")
        
        self._rodape()
        
        return self.asm
    
    def _cabecalho(self):
        self.asm.extend([
            "; ========================================================",
            "; ASSEMBLY AVR - Arduino Uno (ATmega328P)",
            "; Compilador RPN - Fase 4 - FP16 (IEEE 754 Half Precision)",
            "; Autor: João Victor Roth",
            "; PUCPR 2025 - Linguagens Formais e Compiladores",
            "; SAÍDA: Hexadecimal via Serial (9600 baud)",
            "; ========================================================",
            "",
            "; Convenções de Registradores:",
            ";   R16:R17 - Operando A (High:Low)",
            ";   R18:R19 - Operando B (High:Low)",
            ";   R20:R21 - Resultado (High:Low)",
            ";   R22-R31 - Temporários para cálculos FP16",
            "",
            "; ========================================================",
            "; DEFINIÇÕES PARA ATmega328P (compatível com avr-gcc)",
            "; ========================================================",
            "",
            "; Registradores de I/O (endereços de memória)",
            ".equ SPL,    0x3D",
            ".equ SPH,    0x3E",
            ".equ RAMEND, 0x08FF",
            "",
            "; UART Registers",
            ".equ UCSR0A, 0xC0",
            ".equ UCSR0B, 0xC1",
            ".equ UCSR0C, 0xC2",
            ".equ UBRR0L, 0xC4",
            ".equ UBRR0H, 0xC5",
            ".equ UDR0,   0xC6",
            "",
            "; UART Bits",
            ".equ UDRE0,  5",
            ".equ TXEN0,  3",
            ".equ UCSZ01, 2",
            ".equ UCSZ00, 1",
            "",
            "; Status Register",
            ".equ SREG,   0x3F",
            "",
            "; ========================================================",
            "; SEÇÃO DE CÓDIGO",
            "; ========================================================",
            "",
            ".section .text",
            ".global main",
            "",
            "; Vetor de reset",
            ".org 0x0000",
            "    rjmp main",
            "",
            ".org 0x0034",
            "",
            "; Tabela hex para conversão",
            "hex_chars: .ascii \"0123456789ABCDEF\"",
            "",
            "main:",
            "    ; Inicializa Stack Pointer",
            "    ldi r16, lo8(RAMEND)",
            "    out SPL, r16",
            "    ldi r17, hi8(RAMEND)",
            "    out SPH, r17",
            "",
            "    ; Configura Serial 9600 baud (16MHz)",
            "    clr r1",
            "    ldi r16, 103",
            "    sts UBRR0H, r1",
            "    sts UBRR0L, r16",
            "    ldi r16, (1<<TXEN0)",
            "    sts UCSR0B, r16",
            "    ldi r16, (1<<UCSZ01)|(1<<UCSZ00)",
            "    sts UCSR0C, r16",
            "",
            "    ; === INÍCIO DO PROGRAMA ===",
            ""
        ])
    
    def _rodape(self):
        self.asm.extend([
            "",
            "    ; === FIM DO PROGRAMA ===",
            "fim:",
            "    rjmp fim",
            "",
            "; ========================================================",
            "; ROTINAS AUXILIARES",
            "; ========================================================",
            "",
            "; Aguarda UART pronta para transmitir",
            "uart_wait:",
            "    lds r23, UCSR0A",
            "    sbrs r23, UDRE0",
            "    rjmp uart_wait",
            "    ret",
            "",
            "; Envia byte em R20 pela UART",
            "uart_send:",
            "    rcall uart_wait",
            "    sts UDR0, r20",
            "    ret",
            "",
            "; Envia nibble (4 bits) como caractere hex",
            "send_nibble:",
            "    andi r20, 0x0F",
            "    ldi r30, lo8(hex_chars)",
            "    ldi r31, hi8(hex_chars)",
            "    add r30, r20",
            "    adc r31, r1",
            "    lpm r20, Z",
            "    rcall uart_send",
            "    ret",
            "",
            "; Envia byte como 2 caracteres hex",
            "send_hex_byte:",
            "    push r20",
            "    swap r20",
            "    rcall send_nibble",
            "    pop r20",
            "    rcall send_nibble",
            "    ret",
            "",
            "; Envia FP16 (R20:R21) como 0xHHLL (R20=High, R21=Low)",
            "send_fp16_hex:",
            "    push r20",
            "    push r21",
            "    push r22",
            "    ; Envia '0x'",
            "    ldi r20, '0'",
            "    rcall uart_send",
            "    ldi r20, 'x'",
            "    rcall uart_send",
            "    ; Recupera valores originais",
            "    pop r22",
            "    pop r21",
            "    pop r20",
            "    ; Salva para uso posterior",
            "    push r21",
            "    ; Envia High byte (R20)",
            "    rcall send_hex_byte",
            "    ; Envia Low byte (R21)",
            "    pop r20",
            "    rcall send_hex_byte",
            "    ; Envia CR LF",
            "    ldi r20, 0x0D",
            "    rcall uart_send",
            "    ldi r20, 0x0A",
            "    rcall uart_send",
            "    ret",
            "",
            "; ========================================================",
            "; ROTINAS DE ARITMÉTICA FP16 (IEEE 754 Half Precision)",
            "; ========================================================",
            "",
            "; ------------------------------------------------------",
            "; SOMA FP16: R16:R17 + R18:R19 -> R20:R21",
            "; ------------------------------------------------------",
            "fp16_add:",
            "    push r22",
            "    push r23",
            "    push r24",
            "    push r25",
            "    push r26",
            "    push r27",
            "    push r28",
            "    push r29",
            "    push r30",
            "    push r31",
            "",
            "    ; Verifica se A é zero",
            "    mov r22, r16",
            "    andi r22, 0x7F",
            "    or r22, r17",
            "    brne fp16_add_a_nz",
            "    mov r20, r18",
            "    mov r21, r19",
            "    rjmp fp16_add_done",
            "",
            "fp16_add_a_nz:",
            "    ; Verifica se B é zero",
            "    mov r22, r18",
            "    andi r22, 0x7F",
            "    or r22, r19",
            "    brne fp16_add_b_nz",
            "    mov r20, r16",
            "    mov r21, r17",
            "    rjmp fp16_add_done",
            "",
            "fp16_add_b_nz:",
            "    ; Extrai expoente A em R23",
            "    ldi r21, 0x7C",
            "    mov r23, r16",
            "    and r23, r21",
            "    lsr r23",
            "    lsr r23",
            "",
            "    ; Extrai expoente B em R22",
            "    mov r22, r18",
            "    and r22, r21",
            "    lsr r22",
            "    lsr r22",
            "",
            "    ; Compara expoentes",
            "    cp r23, r22",
            "    brlt fp16_add_exp_b_maior",
            "",
            "    ; Caso: Exp A >= Exp B",
            "    mov r31, r23        ; Expoente resultado",
            "    sub r23, r22        ; Diferença de expoentes",
            "    mov r24, r23        ; Contador de shifts",
            "",
            "    ; Mantissa B será alinhada",
            "    ldi r25, 0x03",
            "    mov r26, r18",
            "    and r26, r25",
            "    ori r26, 0x04       ; Hidden bit",
            "    mov r27, r19",
            "",
            "    ; Mantissa A mantém posição",
            "    mov r28, r16",
            "    and r28, r25",
            "    ori r28, 0x04       ; Hidden bit",
            "    mov r29, r17",
            "    rjmp fp16_add_align",
            "",
            "fp16_add_exp_b_maior:",
            "    mov r31, r22        ; Expoente resultado",
            "    sub r22, r23        ; Diferença",
            "    mov r24, r22        ; Contador",
            "",
            "    ; Mantissa A será alinhada",
            "    ldi r25, 0x03",
            "    mov r26, r16",
            "    and r26, r25",
            "    ori r26, 0x04       ; Hidden bit",
            "    mov r27, r17",
            "",
            "    ; Mantissa B mantém posição",
            "    mov r28, r18",
            "    and r28, r25",
            "    ori r28, 0x04       ; Hidden bit",
            "    mov r29, r19",
            "",
            "fp16_add_align:",
            "    ; Alinha mantissa (shift right)",
            "    tst r24",
            "    breq fp16_add_sum",
            "",
            "fp16_add_shift:",
            "    lsr r26",
            "    ror r27",
            "    dec r24",
            "    brne fp16_add_shift",
            "",
            "fp16_add_sum:",
            "    ; Soma mantissas",
            "    add r27, r29",
            "    adc r26, r28",
            "",
            "    ; Verifica overflow (bit 3 setado)",
            "    sbrs r26, 3",
            "    rjmp fp16_add_norm",
            "",
            "    ; Normaliza: shift right e incrementa expoente",
            "    lsr r26",
            "    ror r27",
            "    inc r31",
            "",
            "fp16_add_norm:",
            "    ; Remove hidden bit",
            "    andi r26, 0x03",
            "",
            "    ; Empacota resultado",
            "    mov r20, r31",
            "    lsl r20",
            "    lsl r20",
            "    or r20, r26",
            "    mov r21, r27",
            "",
            "fp16_add_done:",
            "    pop r31",
            "    pop r30",
            "    pop r29",
            "    pop r28",
            "    pop r27",
            "    pop r26",
            "    pop r25",
            "    pop r24",
            "    pop r23",
            "    pop r22",
            "    ret",
            "",
            "; ------------------------------------------------------",
            "; SUBTRAÇÃO FP16: R16:R17 - R18:R19 -> R20:R21",
            "; ------------------------------------------------------",
            "fp16_sub:",
            "    push r2",
            "    push r22",
            "    push r23",
            "    push r24",
            "    push r25",
            "    push r26",
            "    push r27",
            "    push r28",
            "    push r29",
            "    push r30",
            "    push r31",
            "",
            "    clr r30             ; Flag de sinal",
            "",
            "    ; Compara magnitudes (ignora sinal)",
            "    mov r22, r16",
            "    andi r22, 0x7F",
            "    mov r23, r18",
            "    andi r23, 0x7F",
            "",
            "    cp r17, r19",
            "    cpc r22, r23",
            "    brsh fp16_sub_no_swap",
            "",
            "    ; Troca A <-> B",
            "    ldi r30, 1          ; Resultado negativo",
            "    mov r2, r16",
            "    mov r16, r18",
            "    mov r18, r2",
            "    mov r2, r17",
            "    mov r17, r19",
            "    mov r19, r2",
            "",
            "fp16_sub_no_swap:",
            "    ; Extrai expoentes",
            "    ldi r21, 0x7C",
            "    mov r23, r16",
            "    and r23, r21",
            "    lsr r23",
            "    lsr r23",
            "",
            "    mov r22, r18",
            "    and r22, r21",
            "    lsr r22",
            "    lsr r22",
            "",
            "    ; Calcula shift",
            "    mov r31, r23        ; Expoente resultado",
            "    sub r23, r22",
            "    mov r24, r23        ; Contador",
            "",
            "    ; Prepara mantissas com hidden bit",
            "    ldi r25, 0x03",
            "",
            "    mov r26, r18        ; Mantissa menor",
            "    and r26, r25",
            "    ori r26, 0x04",
            "    mov r27, r19",
            "",
            "    mov r28, r16        ; Mantissa maior",
            "    and r28, r25",
            "    ori r28, 0x04",
            "    mov r29, r17",
            "",
            "    ; Alinha mantissa menor",
            "    tst r24",
            "    breq fp16_sub_do",
            "",
            "fp16_sub_shift:",
            "    lsr r26",
            "    ror r27",
            "    dec r24",
            "    brne fp16_sub_shift",
            "",
            "fp16_sub_do:",
            "    ; Subtrai: maior - menor",
            "    sub r29, r27",
            "    sbc r28, r26",
            "",
            "    ; Verifica zero",
            "    mov r25, r28",
            "    or r25, r29",
            "    brne fp16_sub_norm",
            "",
            "    ; Resultado zero",
            "    clr r20",
            "    clr r21",
            "    rjmp fp16_sub_done",
            "",
            "fp16_sub_norm:",
            "    ; Normaliza (shift left até hidden bit em posição)",
            "    sbrc r28, 2",
            "    rjmp fp16_sub_pack",
            "",
            "fp16_sub_norm_loop:",
            "    lsl r29",
            "    rol r28",
            "    dec r31",
            "    sbrs r28, 2",
            "    rjmp fp16_sub_norm_loop",
            "",
            "fp16_sub_pack:",
            "    ; Remove hidden bit e empacota",
            "    andi r28, 0x03",
            "",
            "    mov r20, r31",
            "    lsl r20",
            "    lsl r20",
            "    or r20, r28",
            "",
            "    ; Aplica sinal",
            "    sbrc r30, 0",
            "    ori r20, 0x80",
            "",
            "    mov r21, r29",
            "",
            "fp16_sub_done:",
            "    pop r31",
            "    pop r30",
            "    pop r29",
            "    pop r28",
            "    pop r27",
            "    pop r26",
            "    pop r25",
            "    pop r24",
            "    pop r23",
            "    pop r22",
            "    pop r2",
            "    ret",
            "",
            "; ------------------------------------------------------",
            "; MULTIPLICAÇÃO FP16: R16:R17 * R18:R19 -> R20:R21",
            "; ------------------------------------------------------",
            "fp16_mul:",
            "    push r22",
            "    push r23",
            "    push r24",
            "    push r25",
            "    push r26",
            "    push r27",
            "    push r28",
            "    push r29",
            "    push r30",
            "    push r31",
            "",
            "    ; Verifica zeros - usa trampolin para branch longo",
            "    mov r22, r16",
            "    andi r22, 0x7F",
            "    or r22, r17",
            "    brne fp16_mul_a_nz",
            "    rjmp fp16_mul_zero       ; A é zero",
            "fp16_mul_a_nz:",
            "",
            "    mov r22, r18",
            "    andi r22, 0x7F",
            "    or r22, r19",
            "    brne fp16_mul_b_nz",
            "    rjmp fp16_mul_zero       ; B é zero",
            "fp16_mul_b_nz:",
            "",
            "    ; Calcula sinal (XOR)",
            "    mov r30, r16",
            "    eor r30, r18",
            "    andi r30, 0x80",
            "",
            "    ; Extrai e soma expoentes",
            "    ldi r21, 0x7C",
            "",
            "    mov r23, r16",
            "    and r23, r21",
            "    lsr r23",
            "    lsr r23",
            "",
            "    mov r22, r18",
            "    and r22, r21",
            "    lsr r22",
            "    lsr r22",
            "",
            "    add r23, r22",
            "    subi r23, 15        ; Remove bias",
            "    mov r31, r23        ; Expoente resultado",
            "",
            "    ; Prepara mantissas com hidden bit",
            "    ldi r25, 0x03",
            "",
            "    mov r28, r16",
            "    and r28, r25",
            "    ori r28, 0x04",
            "    mov r27, r17",
            "",
            "    mov r24, r18",
            "    and r24, r25",
            "    ori r24, 0x04",
            "    mov r22, r19",
            "",
            "    ; Multiplicação de mantissas",
            "    clr r29",
            "    clr r26",
            "    clr r25",
            "",
            "    ; Low * Low",
            "    mul r27, r22",
            "    mov r25, r0",
            "    mov r26, r1",
            "",
            "    ; Low * High",
            "    mul r27, r24",
            "    add r26, r0",
            "    adc r29, r1",
            "",
            "    ; High * Low",
            "    mul r28, r22",
            "    add r26, r0",
            "    adc r29, r1",
            "",
            "    ; High * High",
            "    mul r28, r24",
            "    add r29, r0",
            "",
            "    clr r1              ; Limpa R1",
            "",
            "    ; Normaliza se necessário",
            "    sbrs r29, 5",
            "    rjmp fp16_mul_pack",
            "",
            "    lsr r29",
            "    ror r26",
            "    inc r31",
            "",
            "fp16_mul_pack:",
            "    ; Empacota resultado",
            "    mov r20, r31",
            "    lsl r20",
            "    lsl r20",
            "",
            "    mov r24, r29",
            "    lsr r24",
            "    lsr r24",
            "    andi r24, 0x03",
            "    or r20, r24",
            "    or r20, r30         ; Aplica sinal",
            "",
            "    ; Byte baixo",
            "    mov r21, r29",
            "    lsl r21",
            "    lsl r21",
            "    lsl r21",
            "    lsl r21",
            "    lsl r21",
            "    lsl r21",
            "",
            "    mov r24, r26",
            "    lsr r24",
            "    lsr r24",
            "    or r21, r24",
            "",
            "    rjmp fp16_mul_done",
            "",
            "fp16_mul_zero:",
            "    clr r20",
            "    clr r21",
            "",
            "fp16_mul_done:",
            "    pop r31",
            "    pop r30",
            "    pop r29",
            "    pop r28",
            "    pop r27",
            "    pop r26",
            "    pop r25",
            "    pop r24",
            "    pop r23",
            "    pop r22",
            "    ret",
            "",
            "; ------------------------------------------------------",
            "; DIVISÃO FP16: R16:R17 / R18:R19 -> R20:R21",
            "; ------------------------------------------------------",
            "fp16_div:",
            "    push r22",
            "    push r23",
            "    push r24",
            "    push r25",
            "    push r26",
            "    push r27",
            "    push r28",
            "    push r29",
            "    push r30",
            "    push r31",
            "",
            "    ; Verifica divisor zero - usa trampolin",
            "    mov r22, r18",
            "    andi r22, 0x7F",
            "    or r22, r19",
            "    brne fp16_div_b_nz",
            "    rjmp fp16_div_zero",
            "fp16_div_b_nz:",
            "",
            "    ; Verifica dividendo zero",
            "    mov r22, r16",
            "    andi r22, 0x7F",
            "    or r22, r17",
            "    brne fp16_div_a_nz",
            "    rjmp fp16_div_zero",
            "fp16_div_a_nz:",
            "",
            "    ; Calcula sinal",
            "    mov r30, r16",
            "    eor r30, r18",
            "    andi r30, 0x80",
            "",
            "    ; Extrai expoentes",
            "    ldi r21, 0x7C",
            "",
            "    mov r23, r16",
            "    and r23, r21",
            "    lsr r23",
            "    lsr r23",
            "",
            "    mov r22, r18",
            "    and r22, r21",
            "    lsr r22",
            "    lsr r22",
            "",
            "    ; Calcula expoente: ExpA + 15 - ExpB",
            "    ldi r24, 15",
            "    add r23, r24",
            "    sub r23, r22",
            "    mov r31, r23",
            "",
            "    ; Prepara mantissas",
            "    ldi r25, 0x03",
            "",
            "    mov r27, r16        ; Dividendo",
            "    and r27, r25",
            "    ori r27, 0x04",
            "    mov r26, r17",
            "",
            "    mov r29, r18        ; Divisor",
            "    and r29, r25",
            "    ori r29, 0x04",
            "    mov r28, r19",
            "",
            "    ; Loop de divisão (11 iterações)",
            "    ldi r25, 11",
            "    clr r20",
            "    clr r21",
            "",
            "fp16_div_loop:",
            "    lsl r21",
            "    rol r20",
            "",
            "    cp r26, r28",
            "    cpc r27, r29",
            "    brlo fp16_div_no_sub",
            "",
            "    sub r26, r28",
            "    sbc r27, r29",
            "    ori r21, 1",
            "",
            "fp16_div_no_sub:",
            "    lsl r26",
            "    rol r27",
            "",
            "    dec r25",
            "    brne fp16_div_loop",
            "",
            "    ; Normaliza",
            "    sbrc r20, 2",
            "    rjmp fp16_div_pack",
            "",
            "fp16_div_norm:",
            "    lsl r21",
            "    rol r20",
            "    dec r31",
            "    sbrs r20, 2",
            "    rjmp fp16_div_norm",
            "",
            "fp16_div_pack:",
            "    andi r20, 0x03",
            "",
            "    mov r24, r31",
            "    lsl r24",
            "    lsl r24",
            "    or r20, r24",
            "    or r20, r30",
            "",
            "    rjmp fp16_div_done",
            "",
            "fp16_div_zero:",
            "    clr r20",
            "    clr r21",
            "",
            "fp16_div_done:",
            "    pop r31",
            "    pop r30",
            "    pop r29",
            "    pop r28",
            "    pop r27",
            "    pop r26",
            "    pop r25",
            "    pop r24",
            "    pop r23",
            "    pop r22",
            "    ret",
            "",
            "; ------------------------------------------------------",
            "; COMPARAÇÃO FP16: R16:R17 vs R18:R19",
            "; Retorna em R20:R21: 0x3C00 (1.0) se true, 0x0000 se false",
            "; R22 contém tipo de comparação:",
            ";   0 = >, 1 = <, 2 = >=, 3 = <=, 4 = ==, 5 = !=",
            "; ------------------------------------------------------",
            "fp16_cmp:",
            "    push r23",
            "    push r24",
            "",
            "    ; Compara bytes (considerando como unsigned para simplicidade)",
            "    cp r17, r19",
            "    cpc r16, r18",
            "",
            "    ; Guarda flags",
            "    in r23, SREG",
            "",
            "    ; Resultado padrão: false",
            "    clr r20",
            "    clr r21",
            "",
            "    ; Verifica tipo de comparação",
            "    cpi r22, 0          ; >",
            "    brne fp16_cmp_lt",
            "    sbrc r23, 0         ; Se carry=0 e zero=0, então A > B",
            "    rjmp fp16_cmp_done",
            "    sbrc r23, 1",
            "    rjmp fp16_cmp_done",
            "    rjmp fp16_cmp_true",
            "",
            "fp16_cmp_lt:",
            "    cpi r22, 1          ; <",
            "    brne fp16_cmp_ge",
            "    sbrs r23, 0         ; Se carry=1, então A < B",
            "    rjmp fp16_cmp_done",
            "    rjmp fp16_cmp_true",
            "",
            "fp16_cmp_ge:",
            "    cpi r22, 2          ; >=",
            "    brne fp16_cmp_le",
            "    sbrc r23, 0         ; Se carry=0, então A >= B",
            "    rjmp fp16_cmp_done",
            "    rjmp fp16_cmp_true",
            "",
            "fp16_cmp_le:",
            "    cpi r22, 3          ; <=",
            "    brne fp16_cmp_eq",
            "    sbrs r23, 0         ; Se carry=1 ou zero=1",
            "    rjmp fp16_cmp_chk_z",
            "    rjmp fp16_cmp_true",
            "fp16_cmp_chk_z:",
            "    sbrs r23, 1",
            "    rjmp fp16_cmp_done",
            "    rjmp fp16_cmp_true",
            "",
            "fp16_cmp_eq:",
            "    cpi r22, 4          ; ==",
            "    brne fp16_cmp_ne",
            "    sbrs r23, 1         ; Se zero=1",
            "    rjmp fp16_cmp_done",
            "    rjmp fp16_cmp_true",
            "",
            "fp16_cmp_ne:",
            "    ; !=",
            "    sbrc r23, 1         ; Se zero=0",
            "    rjmp fp16_cmp_done",
            "    rjmp fp16_cmp_true",
            "",
            "fp16_cmp_true:",
            "    ldi r20, 0x3C       ; 1.0 em FP16",
            "    clr r21",
            "",
            "fp16_cmp_done:",
            "    pop r24",
            "    pop r23",
            "    ret",
            ""
        ])
    
    def _alocar(self, var: str) -> int:
        """Aloca endereço de memória para variável."""
        if var not in self.variaveis:
            self.variaveis[var] = self.prox_end
            self.prox_end += 2  # FP16 = 2 bytes
        return self.variaveis[var]
    
    def _novo_label(self, prefix: str = "L") -> str:
        l = f"{prefix}_{self.label_count}"
        self.label_count += 1
        return l
    
    def _eh_numero(self, val: str) -> bool:
        if val is None:
            return False
        try:
            float(val)
            return True
        except:
            return False
    
    def _processar(self, inst: InstrucaoTAC):
        self.asm.append(f"")
        self.asm.append(f"    ; TAC: {inst}")
        
        if inst.tipo == "ASSIGN":
            self._gerar_assign(inst)
        elif inst.tipo == "BINOP":
            self._gerar_binop(inst)
        elif inst.tipo == "LOAD":
            self._gerar_load(inst)
        elif inst.tipo == "STORE":
            self._gerar_store(inst)
        elif inst.tipo == "LABEL":
            self.asm.append(f"{inst.label}:")
        elif inst.tipo == "GOTO":
            self.asm.append(f"    rjmp {inst.label}")
        elif inst.tipo == "IFFALSE":
            self._gerar_iffalse(inst)
        elif inst.tipo == "PRINT":
            self._gerar_print(inst)
    
    def _gerar_assign(self, inst: InstrucaoTAC):
        end = self._alocar(inst.destino)
        
        if self._eh_numero(inst.op1):
            h, l = self.converter.float_to_fp16(float(inst.op1))
            self.asm.extend([
                f"    ldi r16, 0x{h:02X}",
                f"    ldi r17, 0x{l:02X}",
                f"    sts 0x{end:04X}, r16",
                f"    sts 0x{end+1:04X}, r17"
            ])
        else:
            src = self._alocar(inst.op1)
            self.asm.extend([
                f"    lds r16, 0x{src:04X}",
                f"    lds r17, 0x{src+1:04X}",
                f"    sts 0x{end:04X}, r16",
                f"    sts 0x{end+1:04X}, r17"
            ])
    
    def _gerar_load(self, inst: InstrucaoTAC):
        src = self._alocar(inst.op1)
        dest = self._alocar(inst.destino)
        self.asm.extend([
            f"    lds r16, 0x{src:04X}",
            f"    lds r17, 0x{src+1:04X}",
            f"    sts 0x{dest:04X}, r16",
            f"    sts 0x{dest+1:04X}, r17"
        ])
    
    def _gerar_store(self, inst: InstrucaoTAC):
        end = self._alocar(inst.op1)
        
        if self._eh_numero(inst.op2):
            h, l = self.converter.float_to_fp16(float(inst.op2))
            self.asm.extend([
                f"    ldi r16, 0x{h:02X}",
                f"    ldi r17, 0x{l:02X}",
                f"    sts 0x{end:04X}, r16",
                f"    sts 0x{end+1:04X}, r17"
            ])
        else:
            src = self._alocar(inst.op2)
            self.asm.extend([
                f"    lds r16, 0x{src:04X}",
                f"    lds r17, 0x{src+1:04X}",
                f"    sts 0x{end:04X}, r16",
                f"    sts 0x{end+1:04X}, r17"
            ])
    
    def _gerar_binop(self, inst: InstrucaoTAC):
        dest = self._alocar(inst.destino)
        
        # Carrega operando A em R16:R17
        if self._eh_numero(inst.op1):
            h, l = self.converter.float_to_fp16(float(inst.op1))
            self.asm.extend([
                f"    ldi r16, 0x{h:02X}",
                f"    ldi r17, 0x{l:02X}"
            ])
        else:
            a1 = self._alocar(inst.op1)
            self.asm.extend([
                f"    lds r16, 0x{a1:04X}",
                f"    lds r17, 0x{a1+1:04X}"
            ])
        
        # Carrega operando B em R18:R19
        if self._eh_numero(inst.op2):
            h, l = self.converter.float_to_fp16(float(inst.op2))
            self.asm.extend([
                f"    ldi r18, 0x{h:02X}",
                f"    ldi r19, 0x{l:02X}"
            ])
        else:
            a2 = self._alocar(inst.op2)
            self.asm.extend([
                f"    lds r18, 0x{a2:04X}",
                f"    lds r19, 0x{a2+1:04X}"
            ])
        
        # Chama rotina apropriada
        if inst.operador == '+':
            self.asm.append("    rcall fp16_add")
        elif inst.operador == '-':
            self.asm.append("    rcall fp16_sub")
        elif inst.operador == '*':
            self.asm.append("    rcall fp16_mul")
        elif inst.operador in ['/', '|']:
            self.asm.append("    rcall fp16_div")
        elif inst.operador == '>':
            self.asm.extend([
                "    ldi r22, 0",
                "    rcall fp16_cmp"
            ])
        elif inst.operador == '<':
            self.asm.extend([
                "    ldi r22, 1",
                "    rcall fp16_cmp"
            ])
        elif inst.operador == '>=':
            self.asm.extend([
                "    ldi r22, 2",
                "    rcall fp16_cmp"
            ])
        elif inst.operador == '<=':
            self.asm.extend([
                "    ldi r22, 3",
                "    rcall fp16_cmp"
            ])
        elif inst.operador == '==':
            self.asm.extend([
                "    ldi r22, 4",
                "    rcall fp16_cmp"
            ])
        elif inst.operador == '!=':
            self.asm.extend([
                "    ldi r22, 5",
                "    rcall fp16_cmp"
            ])
        else:
            self.asm.append(f"    ; Operador não implementado: {inst.operador}")
            self.asm.extend(["    clr r20", "    clr r21"])
        
        # Salva resultado
        self.asm.extend([
            f"    sts 0x{dest:04X}, r20",
            f"    sts 0x{dest+1:04X}, r21"
        ])
    
    def _gerar_iffalse(self, inst: InstrucaoTAC):
        if self._eh_numero(inst.op1):
            val = float(inst.op1)
            if val == 0:
                self.asm.append(f"    rjmp {inst.label}")
        else:
            end = self._alocar(inst.op1)
            # Usa trampolin para branches longos
            # Em vez de breq label (que só alcança ±64 instruções)
            # Usamos brne skip + rjmp label
            skip_label = f"_skip_{self.label_count}"
            self.label_count += 1
            self.asm.extend([
                f"    lds r24, 0x{end:04X}",
                f"    lds r25, 0x{end+1:04X}",
                f"    or r24, r25",
                f"    brne {skip_label}",      # Se não é zero, pula o rjmp
                f"    rjmp {inst.label}",      # Se é zero, salta para o label
                f"{skip_label}:"
            ])
    
    def _gerar_print(self, inst: InstrucaoTAC):
        if self._eh_numero(inst.op1):
            h, l = self.converter.float_to_fp16(float(inst.op1))
            self.asm.extend([
                f"    ldi r20, 0x{h:02X}",
                f"    ldi r21, 0x{l:02X}",
                f"    rcall send_fp16_hex"
            ])
        else:
            end = self._alocar(inst.op1)
            self.asm.extend([
                f"    lds r20, 0x{end:04X}",
                f"    lds r21, 0x{end+1:04X}",
                f"    rcall send_fp16_hex"
            ])


# ============================================================================
# INTEGRAÇÃO TOOLCHAIN AVR
# ============================================================================

class AVRToolchain:
    """
    Integração com a toolchain AVR para compilação e upload.
    Suporta Mac (ARM/Intel), Linux e Windows.
    
    Fluxo:
    1. Salvar assembly como .s
    2. Compilar .s -> .elf usando avr-gcc -nostdlib
    3. Extrair .elf -> .hex usando avr-objcopy
    4. Upload .hex -> Arduino usando avrdude
    """
    
    # Configurações do ATmega328P (Arduino Uno)
    MCU = "atmega328p"
    F_CPU = "16000000"  # 16 MHz
    BAUD_RATE = "115200"  # Baud rate para upload
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.sistema = platform.system()  # 'Darwin', 'Linux', 'Windows'
        self.arch = platform.machine()    # 'arm64', 'x86_64', etc.
        
    def _log(self, msg: str):
        """Imprime mensagem se verbose estiver ativado."""
        if self.verbose:
            print(f"  [AVR] {msg}")
    
    def _executar(self, cmd: List[str], descricao: str) -> Tuple[bool, str, str]:
        """
        Executa um comando e retorna (sucesso, stdout, stderr).
        """
        self._log(f"{descricao}...")
        self._log(f"  Comando: {' '.join(cmd)}")
        
        try:
            resultado = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 60 segundos de timeout
            )
            
            if resultado.returncode == 0:
                self._log(f"  ✓ Sucesso")
                return True, resultado.stdout, resultado.stderr
            else:
                self._log(f"  ✗ Erro (código {resultado.returncode})")
                if resultado.stderr:
                    for linha in resultado.stderr.split('\n')[:5]:
                        if linha.strip():
                            self._log(f"    {linha}")
                return False, resultado.stdout, resultado.stderr
                
        except FileNotFoundError:
            self._log(f"  ✗ Comando não encontrado: {cmd[0]}")
            return False, "", f"Comando não encontrado: {cmd[0]}"
        except subprocess.TimeoutExpired:
            self._log(f"  ✗ Timeout expirado")
            return False, "", "Timeout expirado"
        except Exception as e:
            self._log(f"  ✗ Exceção: {str(e)}")
            return False, "", str(e)
    
    def verificar_toolchain(self) -> Dict[str, bool]:
        """
        Verifica se as ferramentas AVR estão instaladas.
        Retorna dict com status de cada ferramenta.
        """
        ferramentas = {
            "avr-gcc": False,
            "avr-objcopy": False,
            "avrdude": False
        }
        
        self._log("Verificando toolchain AVR...")
        
        for ferramenta in ferramentas:
            try:
                resultado = subprocess.run(
                    [ferramenta, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if resultado.returncode == 0:
                    ferramentas[ferramenta] = True
                    # Extrai versão da primeira linha
                    versao = resultado.stdout.split('\n')[0].strip()
                    self._log(f"  ✓ {ferramenta}: {versao[:60]}")
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._log(f"  ✗ {ferramenta}: não encontrado")
        
        return ferramentas
    
    def detectar_porta_serial(self) -> Optional[str]:
        """
        Detecta automaticamente a porta serial do Arduino.
        Suporta Mac, Linux e Windows.
        """
        self._log("Detectando porta serial...")
        
        if self.sistema == "Darwin":  # macOS
            # Padrões comuns no Mac
            padroes = [
                "/dev/tty.usbmodem*",
                "/dev/tty.usbserial*",
                "/dev/cu.usbmodem*",
                "/dev/cu.usbserial*"
            ]
            for padrao in padroes:
                portas = glob.glob(padrao)
                if portas:
                    porta = sorted(portas)[0]  # Pega a primeira
                    self._log(f"  ✓ Encontrado: {porta}")
                    return porta
                    
        elif self.sistema == "Linux":
            # Padrões comuns no Linux
            padroes = [
                "/dev/ttyUSB*",
                "/dev/ttyACM*"
            ]
            for padrao in padroes:
                portas = glob.glob(padrao)
                if portas:
                    porta = sorted(portas)[0]
                    self._log(f"  ✓ Encontrado: {porta}")
                    return porta
                    
        elif self.sistema == "Windows":
            # No Windows, lista portas COM
            import serial.tools.list_ports
            portas = serial.tools.list_ports.comports()
            for porta in portas:
                if "Arduino" in porta.description or "CH340" in porta.description:
                    self._log(f"  ✓ Encontrado: {porta.device}")
                    return porta.device
            # Se não encontrou especificamente Arduino, retorna primeira porta
            if portas:
                self._log(f"  ✓ Usando: {portas[0].device}")
                return portas[0].device
        
        self._log("  ✗ Nenhuma porta serial encontrada")
        return None
    
    def salvar_assembly(self, asm_lines: List[str], arquivo_s: str) -> bool:
        """
        Salva o assembly com extensão .s (necessário para avr-gcc).
        """
        self._log(f"Salvando assembly: {arquivo_s}")
        
        try:
            with open(arquivo_s, 'w', encoding='utf-8') as f:
                for linha in asm_lines:
                    f.write(linha + '\n')
            
            linhas = len(asm_lines)
            tamanho = os.path.getsize(arquivo_s)
            self._log(f"  ✓ {linhas} linhas, {tamanho} bytes")
            return True
            
        except Exception as e:
            self._log(f"  ✗ Erro ao salvar: {str(e)}")
            return False
    
    def compilar_para_elf(self, arquivo_s: str, arquivo_elf: str) -> bool:
        """
        Compila o arquivo .s para .elf usando avr-gcc.
        Usa -nostdlib pois o assembly é completo (sem runtime C).
        """
        cmd = [
            "avr-gcc",
            "-mmcu=" + self.MCU,
            "-nostdlib",          # Não usa biblioteca padrão C
            "-o", arquivo_elf,
            arquivo_s
        ]
        
        sucesso, stdout, stderr = self._executar(cmd, f"Compilando {arquivo_s} -> {arquivo_elf}")
        
        if sucesso and os.path.exists(arquivo_elf):
            tamanho = os.path.getsize(arquivo_elf)
            self._log(f"  Tamanho ELF: {tamanho} bytes")
            return True
        
        return False
    
    def extrair_hex(self, arquivo_elf: str, arquivo_hex: str) -> bool:
        """
        Extrai o arquivo .hex a partir do .elf usando avr-objcopy.
        Formato Intel HEX é o padrão para upload no Arduino.
        """
        cmd = [
            "avr-objcopy",
            "-O", "ihex",           # Formato Intel HEX
            "-R", ".eeprom",        # Remove seção EEPROM (não usamos)
            arquivo_elf,
            arquivo_hex
        ]
        
        sucesso, stdout, stderr = self._executar(cmd, f"Extraindo {arquivo_elf} -> {arquivo_hex}")
        
        if sucesso and os.path.exists(arquivo_hex):
            tamanho = os.path.getsize(arquivo_hex)
            # Conta linhas do HEX para estimar tamanho do programa
            with open(arquivo_hex, 'r') as f:
                linhas = len(f.readlines())
            self._log(f"  Tamanho HEX: {tamanho} bytes ({linhas} linhas)")
            return True
        
        return False
    
    def upload_arduino(self, arquivo_hex: str, porta: Optional[str] = None) -> bool:
        """
        Faz upload do arquivo .hex para o Arduino usando avrdude.
        Se porta não for especificada, tenta detectar automaticamente.
        """
        if porta is None:
            porta = self.detectar_porta_serial()
            if porta is None:
                self._log("✗ Não foi possível detectar a porta serial")
                self._log("  Conecte o Arduino e tente novamente")
                self._log("  Ou especifique a porta manualmente: --port /dev/tty.usbmodem*")
                return False
        
        cmd = [
            "avrdude",
            "-p", self.MCU,           # Microcontrolador
            "-c", "arduino",          # Programador (bootloader Arduino)
            "-P", porta,              # Porta serial
            "-b", self.BAUD_RATE,     # Baud rate
            "-U", f"flash:w:{arquivo_hex}:i"  # Upload para flash, formato Intel HEX
        ]
        
        sucesso, stdout, stderr = self._executar(cmd, f"Upload para Arduino em {porta}")
        
        if sucesso:
            self._log("  ✓ Upload concluído com sucesso!")
            self._log(f"  Abra o Serial Monitor (9600 baud) para ver a saída")
        
        return sucesso
    
    def build_completo(self, asm_lines: List[str], base_nome: str, 
                       fazer_upload: bool = False, porta: Optional[str] = None) -> Dict[str, Any]:
        """
        Executa o build completo: .s -> .elf -> .hex (-> upload opcional).
        
        Args:
            asm_lines: Linhas de código assembly
            base_nome: Nome base para os arquivos (sem extensão)
            fazer_upload: Se True, faz upload para Arduino
            porta: Porta serial (ou None para detectar)
        
        Returns:
            Dict com status de cada etapa e caminhos dos arquivos
        """
        resultado = {
            "sucesso": False,
            "arquivo_s": f"{base_nome}.s",
            "arquivo_elf": f"{base_nome}.elf",
            "arquivo_hex": f"{base_nome}.hex",
            "etapas": {
                "assembly": False,
                "elf": False,
                "hex": False,
                "upload": False
            },
            "erros": []
        }
        
        print("\n" + "━" * 60)
        print("BUILD AVR TOOLCHAIN")
        print("━" * 60)
        
        # Verifica toolchain
        tools = self.verificar_toolchain()
        if not all([tools["avr-gcc"], tools["avr-objcopy"]]):
            resultado["erros"].append("Toolchain AVR não está completa")
            print("\n⚠️  Instale a toolchain AVR:")
            if self.sistema == "Darwin":
                print("    brew install avr-gcc")
                print("    brew install avrdude")
            elif self.sistema == "Linux":
                print("    sudo apt install gcc-avr avr-libc avrdude")
            return resultado
        
        # Etapa 1: Salvar .s
        if not self.salvar_assembly(asm_lines, resultado["arquivo_s"]):
            resultado["erros"].append("Falha ao salvar assembly")
            return resultado
        resultado["etapas"]["assembly"] = True
        
        # Etapa 2: Compilar .s -> .elf
        if not self.compilar_para_elf(resultado["arquivo_s"], resultado["arquivo_elf"]):
            resultado["erros"].append("Falha na compilação para ELF")
            return resultado
        resultado["etapas"]["elf"] = True
        
        # Etapa 3: Extrair .elf -> .hex
        if not self.extrair_hex(resultado["arquivo_elf"], resultado["arquivo_hex"]):
            resultado["erros"].append("Falha na extração do HEX")
            return resultado
        resultado["etapas"]["hex"] = True
        
        # Etapa 4: Upload (opcional)
        if fazer_upload:
            if not tools["avrdude"]:
                resultado["erros"].append("avrdude não encontrado para upload")
            else:
                resultado["etapas"]["upload"] = self.upload_arduino(resultado["arquivo_hex"], porta)
        
        resultado["sucesso"] = resultado["etapas"]["hex"]
        return resultado


# ============================================================================
# FUNÇÕES DE SALVAMENTO
# ============================================================================

def salvar_tokens(tokens: List[Token], arquivo: str):
    dados = {"fase": "1", "tokens": [t.para_dict() for t in tokens]}
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def salvar_ast(arvores: List[Dict], arquivo: str):
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump({"fase": "2", "arvores": arvores}, f, indent=2, ensure_ascii=False)


def salvar_ast_atribuida(arvores: List[Dict], tabela: Dict, arquivo: str):
    with open(arquivo, 'w', encoding='utf-8') as f:
        json.dump({"fase": "3", "tabela_simbolos": tabela, "arvores": arvores}, 
                  f, indent=2, ensure_ascii=False)


def salvar_tac(instrucoes: List[InstrucaoTAC], arquivo: str, otimizado: bool = False):
    with open(arquivo, 'w', encoding='utf-8') as f:
        f.write(f"# TAC {'OTIMIZADO ' if otimizado else ''}\n")
        f.write(f"# {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        for inst in instrucoes:
            f.write(str(inst) + '\n')


# ============================================================================
# MAIN
# ============================================================================

def print_ajuda():
    """Imprime ajuda de uso do compilador."""
    print("""
COMPILADOR RPN - FASE 4 COM FP16
PUCPR 2025 - João Victor Roth

USO:
    python compilador_fase4_fp16.py <arquivo.txt> [opções]

OPÇÕES:
    --upload          Faz upload automático para o Arduino
    --port <porta>    Especifica porta serial (ex: /dev/tty.usbmodem14101)
    --no-build        Apenas gera .s, não compila .elf/.hex
    --help            Mostra esta ajuda

EXEMPLOS:
    python compilador_fase4_fp16.py fatorial.txt
    python compilador_fase4_fp16.py fatorial.txt --upload
    python compilador_fase4_fp16.py fatorial.txt --upload --port /dev/cu.usbmodem14101
    python compilador_fase4_fp16.py fibonacci.txt --no-build

ARQUIVOS GERADOS:
    <nome>_tokens.json        - Tokens (Fase 1)
    <nome>_ast.json           - AST (Fase 2)
    <nome>_ast_atribuida.json - AST atribuída (Fase 3)
    <nome>_tac.txt            - TAC original
    <nome>_tac_otimizado.txt  - TAC otimizado
    <nome>_relatorio.md       - Relatório de otimizações
    <nome>.s                  - Assembly AVR
    <nome>.elf                - Binário ELF
    <nome>.hex                - Intel HEX para Arduino
""")


def main():
    print("\n" + "=" * 60)
    print("COMPILADOR RPN - FASE 4 COM FP16")
    print("PUCPR 2025 - João Victor Roth")
    print("=" * 60 + "\n")
    
    # Parse de argumentos
    args = sys.argv[1:]
    
    if not args or "--help" in args:
        print_ajuda()
        sys.exit(0 if "--help" in args else 1)
    
    arquivo = None
    fazer_upload = "--upload" in args
    fazer_build = "--no-build" not in args
    porta_serial = None
    
    # Procura arquivo e porta
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            porta_serial = args[i + 1]
            i += 2
        elif not args[i].startswith("--") and arquivo is None:
            arquivo = args[i]
            i += 1
        else:
            i += 1
    
    if arquivo is None:
        print("Erro: Nenhum arquivo especificado")
        print("Uso: python compilador_fase4_fp16.py <arquivo.txt>")
        sys.exit(1)
    
    base = os.path.splitext(arquivo)[0]
    
    try:
        with open(arquivo, 'r', encoding='utf-8') as f:
            codigo = f.read()
    except FileNotFoundError:
        print(f"Erro: Arquivo '{arquivo}' não encontrado")
        sys.exit(1)
    
    print(f"📂 Processando: {arquivo}\n")
    
    # === FASES 1-3 ===
    print("━" * 60)
    print("FASES 1-3: Análise Léxica, Sintática e Semântica")
    print("━" * 60)
    
    todos_tokens = []
    tabela_simbolos = {}
    arvores = []
    arvores_dict = []
    
    linhas = codigo.strip().split('\n')
    
    for i, linha in enumerate(linhas, 1):
        linha_limpa = linha.strip()
        if not linha_limpa or linha_limpa.startswith('#'):
            continue
        
        # Remove comentários inline
        if '//' in linha_limpa:
            linha_limpa = linha_limpa.split('//')[0].strip()
            if not linha_limpa:
                continue
        
        print(f"\n→ Linha {i}: {linha_limpa[:50]}{'...' if len(linha_limpa) > 50 else ''}")
        
        lexer = AnalisadorLexico(linha_limpa, i)
        tokens = lexer.tokenizar()
        todos_tokens.extend(tokens[:-1])
        
        parser = ParserRPN(tokens, tabela_simbolos)
        arvore, erros = parser.parse()
        
        if erros:
            for e in erros:
                print(f"  ✗ Erro: {e}")
        elif arvore:
            print(f"  ✓ OK: {arvore.tipo}")
            arvores.append({'linha': i, 'arvore': arvore})
            arvores_dict.append({'linha': i, 'ast': arvore.para_dict()})
    
    # Salva Fases 1-3
    salvar_tokens(todos_tokens, f"{base}_tokens.json")
    salvar_ast(arvores_dict, f"{base}_ast.json")
    salvar_ast_atribuida(arvores_dict, tabela_simbolos, f"{base}_ast_atribuida.json")
    
    print(f"\n✓ Tokens: {base}_tokens.json")
    print(f"✓ AST: {base}_ast.json")
    print(f"✓ AST Atribuída: {base}_ast_atribuida.json")
    
    # === FASE 4.1: TAC ===
    print("\n" + "━" * 60)
    print("FASE 4.1: Geração de TAC")
    print("━" * 60)
    
    gerador_tac = GeradorTAC()
    todas_instrucoes = []
    
    for item in arvores:
        instrucoes = gerador_tac.gerar(item['arvore'])
        todas_instrucoes.extend(instrucoes)
    
    salvar_tac(todas_instrucoes, f"{base}_tac.txt")
    print(f"\n✓ TAC: {base}_tac.txt ({len(todas_instrucoes)} instruções)")
    
    # Mostra TAC
    print("\n--- TAC GERADO ---")
    for inst in todas_instrucoes[:30]:
        print(str(inst))
    if len(todas_instrucoes) > 30:
        print(f"... ({len(todas_instrucoes) - 30} mais)")
    
    # === FASE 4.2: OTIMIZAÇÃO ===
    print("\n" + "━" * 60)
    print("FASE 4.2: Otimização")
    print("━" * 60)
    
    otimizador = OtimizadorTAC()
    tac_otimizado = otimizador.otimizar(todas_instrucoes)
    
    salvar_tac(tac_otimizado, f"{base}_tac_otimizado.txt", otimizado=True)
    
    with open(f"{base}_relatorio.md", 'w', encoding='utf-8') as f:
        f.write(otimizador.gerar_relatorio())
    
    print(f"\n✓ TAC otimizado: {base}_tac_otimizado.txt")
    print(f"✓ Relatório: {base}_relatorio.md")
    print(f"  CF:{otimizador.stats['constant_folding']} CP:{otimizador.stats['constant_propagation']} DCE:{otimizador.stats['dead_code']}")
    
    # === FASE 4.3: ASSEMBLY ===
    print("\n" + "━" * 60)
    print("FASE 4.3: Geração de Assembly AVR")
    print("━" * 60)
    
    gerador_asm = GeradorAssembly()
    asm = gerador_asm.gerar(tac_otimizado)
    
    print(f"\n✓ Assembly gerado: {len(asm)} linhas")
    
    # === BUILD AVR ===
    toolchain = AVRToolchain(verbose=True)
    
    if fazer_build:
        resultado_build = toolchain.build_completo(
            asm_lines=asm,
            base_nome=base,
            fazer_upload=fazer_upload,
            porta=porta_serial
        )
        
        if resultado_build["sucesso"]:
            print("\n" + "=" * 60)
            print("✅ BUILD COMPLETO!")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("⚠️  BUILD COM PROBLEMAS")
            print("=" * 60)
            for erro in resultado_build["erros"]:
                print(f"  • {erro}")
    else:
        # Apenas salva .s sem compilar
        toolchain.salvar_assembly(asm, f"{base}.s")
        print(f"\n✓ Assembly salvo: {base}.s (sem build)")
    
    # Resumo final
    print("\n" + "=" * 60)
    print("ARQUIVOS GERADOS")
    print("=" * 60)
    
    arquivos_gerados = [
        f"{base}_tokens.json",
        f"{base}_ast.json",
        f"{base}_ast_atribuida.json",
        f"{base}_tac.txt",
        f"{base}_tac_otimizado.txt",
        f"{base}_relatorio.md",
        f"{base}.s"
    ]
    
    if fazer_build:
        arquivos_gerados.extend([f"{base}.elf", f"{base}.hex"])
    
    for arq in arquivos_gerados:
        if os.path.exists(arq):
            tamanho = os.path.getsize(arq)
            print(f"  ✓ {arq} ({tamanho} bytes)")
        else:
            print(f"  ✗ {arq} (não gerado)")
    
    print("\n📊 Tabela de símbolos:")
    for nome, info in tabela_simbolos.items():
        print(f"   • {nome}: {info.get('tipo', 'real')}")
    
    if fazer_build and os.path.exists(f"{base}.hex"):
        print("\n✅ Para testar no Arduino:")
        print(f"   1. Conecte o Arduino Uno")
        if not fazer_upload:
            print(f"   2. Execute: python compilador_fase4_fp16.py {arquivo} --upload")
        print(f"   3. Abra Serial Monitor (9600 baud)")
        print(f"   4. Saída em formato 0xHHLL (FP16 hexadecimal)")
    
    print()


if __name__ == "__main__":
    main()
