; ========================================================
; ASSEMBLY AVR - Arduino Uno (ATmega328P)
; Compilador RPN - Fase 4 - FP16 (IEEE 754 Half Precision)
; Autor: João Victor Roth
; PUCPR 2025 - Linguagens Formais e Compiladores
; SAÍDA: Hexadecimal via Serial (9600 baud)
; ========================================================

; Convenções de Registradores:
;   R16:R17 - Operando A (High:Low)
;   R18:R19 - Operando B (High:Low)
;   R20:R21 - Resultado (High:Low)
;   R22-R31 - Temporários para cálculos FP16

; ========================================================
; DEFINIÇÕES PARA ATmega328P (compatível com avr-gcc)
; ========================================================

; Registradores de I/O (endereços de memória)
.equ SPL,    0x3D
.equ SPH,    0x3E
.equ RAMEND, 0x08FF

; UART Registers
.equ UCSR0A, 0xC0
.equ UCSR0B, 0xC1
.equ UCSR0C, 0xC2
.equ UBRR0L, 0xC4
.equ UBRR0H, 0xC5
.equ UDR0,   0xC6

; UART Bits
.equ UDRE0,  5
.equ TXEN0,  3
.equ UCSZ01, 2
.equ UCSZ00, 1

; Status Register
.equ SREG,   0x3F

; ========================================================
; SEÇÃO DE CÓDIGO
; ========================================================

.section .text
.global main

; Vetor de reset
.org 0x0000
    rjmp main

.org 0x0034

; Tabela hex para conversão
hex_chars: .ascii "0123456789ABCDEF"

main:
    ; Inicializa Stack Pointer
    ldi r16, lo8(RAMEND)
    out SPL, r16
    ldi r17, hi8(RAMEND)
    out SPH, r17

    ; Configura Serial 9600 baud (16MHz)
    clr r1
    ldi r16, 103
    sts UBRR0H, r1
    sts UBRR0L, r16
    ldi r16, (1<<TXEN0)
    sts UCSR0B, r16
    ldi r16, (1<<UCSZ01)|(1<<UCSZ00)
    sts UCSR0C, r16

    ; === INÍCIO DO PROGRAMA ===


    ; TAC:     MEM[A] = 0
    ldi r16, 0x00
    ldi r17, 0x00
    sts 0x0200, r16
    sts 0x0201, r17

    ; TAC:     MEM[B] = 1
    ldi r16, 0x3C
    ldi r17, 0x00
    sts 0x0202, r16
    sts 0x0203, r17

    ; TAC:     MEM[I] = 0
    ldi r16, 0x00
    ldi r17, 0x00
    sts 0x0204, r16
    sts 0x0205, r17

    ; TAC:     MEM[LIMIT] = 24
    ldi r16, 0x4E
    ldi r17, 0x00
    sts 0x0206, r16
    sts 0x0207, r17
    ; === INÍCIO WHILE ===

    ; TAC: WHILE_INICIO0:
WHILE_INICIO0:
    ; --- Condição ---

    ; TAC:     t0 = MEM[I]
    lds r16, 0x0204
    lds r17, 0x0205
    sts 0x0208, r16
    sts 0x0209, r17

    ; TAC:     t1 = MEM[LIMIT]
    lds r16, 0x0206
    lds r17, 0x0207
    sts 0x020A, r16
    sts 0x020B, r17

    ; TAC:     t2 = t0 < t1
    lds r16, 0x0208
    lds r17, 0x0209
    lds r18, 0x020A
    lds r19, 0x020B
    ldi r22, 1
    rcall fp16_cmp
    sts 0x020C, r20
    sts 0x020D, r21

    ; TAC:     ifFalse t2 goto WHILE_FIM1
    lds r24, 0x020C
    lds r25, 0x020D
    or r24, r25
    brne _skip_0
    rjmp WHILE_FIM1
_skip_0:
    ; --- Corpo ---

    ; TAC:     t3 = MEM[A]
    lds r16, 0x0200
    lds r17, 0x0201
    sts 0x020E, r16
    sts 0x020F, r17

    ; TAC:     print t3
    lds r20, 0x020E
    lds r21, 0x020F
    rcall send_fp16_hex

    ; TAC:     t4 = MEM[A]
    lds r16, 0x0200
    lds r17, 0x0201
    sts 0x0210, r16
    sts 0x0211, r17

    ; TAC:     t5 = MEM[B]
    lds r16, 0x0202
    lds r17, 0x0203
    sts 0x0212, r16
    sts 0x0213, r17

    ; TAC:     t6 = t4 + t5
    lds r16, 0x0210
    lds r17, 0x0211
    lds r18, 0x0212
    lds r19, 0x0213
    rcall fp16_add
    sts 0x0214, r20
    sts 0x0215, r21

    ; TAC:     MEM[TEMP] = t6
    lds r16, 0x0214
    lds r17, 0x0215
    sts 0x0216, r16
    sts 0x0217, r17

    ; TAC:     t7 = MEM[B]
    lds r16, 0x0202
    lds r17, 0x0203
    sts 0x0218, r16
    sts 0x0219, r17

    ; TAC:     MEM[A] = t7
    lds r16, 0x0218
    lds r17, 0x0219
    sts 0x0200, r16
    sts 0x0201, r17

    ; TAC:     t8 = MEM[TEMP]
    lds r16, 0x0216
    lds r17, 0x0217
    sts 0x021A, r16
    sts 0x021B, r17

    ; TAC:     MEM[B] = t8
    lds r16, 0x021A
    lds r17, 0x021B
    sts 0x0202, r16
    sts 0x0203, r17

    ; TAC:     t9 = MEM[I]
    lds r16, 0x0204
    lds r17, 0x0205
    sts 0x021C, r16
    sts 0x021D, r17

    ; TAC:     t10 = t9 + 1
    lds r16, 0x021C
    lds r17, 0x021D
    ldi r18, 0x3C
    ldi r19, 0x00
    rcall fp16_add
    sts 0x021E, r20
    sts 0x021F, r21

    ; TAC:     MEM[I] = t10
    lds r16, 0x021E
    lds r17, 0x021F
    sts 0x0204, r16
    sts 0x0205, r17

    ; TAC:     goto WHILE_INICIO0
    rjmp WHILE_INICIO0

    ; TAC: WHILE_FIM1:
WHILE_FIM1:
    ; === FIM WHILE ===

    ; === FIM DO PROGRAMA ===
fim:
    rjmp fim

; ========================================================
; ROTINAS AUXILIARES
; ========================================================

; Aguarda UART pronta para transmitir
uart_wait:
    lds r23, UCSR0A
    sbrs r23, UDRE0
    rjmp uart_wait
    ret

; Envia byte em R20 pela UART
uart_send:
    rcall uart_wait
    sts UDR0, r20
    ret

; Envia nibble (4 bits) como caractere hex
send_nibble:
    andi r20, 0x0F
    ldi r30, lo8(hex_chars)
    ldi r31, hi8(hex_chars)
    add r30, r20
    adc r31, r1
    lpm r20, Z
    rcall uart_send
    ret

; Envia byte como 2 caracteres hex
send_hex_byte:
    push r20
    swap r20
    rcall send_nibble
    pop r20
    rcall send_nibble
    ret

; Envia FP16 (R20:R21) como 0xHHLL (R20=High, R21=Low)
send_fp16_hex:
    push r20
    push r21
    push r22
    ; Envia '0x'
    ldi r20, '0'
    rcall uart_send
    ldi r20, 'x'
    rcall uart_send
    ; Recupera valores originais
    pop r22
    pop r21
    pop r20
    ; Salva para uso posterior
    push r21
    ; Envia High byte (R20)
    rcall send_hex_byte
    ; Envia Low byte (R21)
    pop r20
    rcall send_hex_byte
    ; Envia CR LF
    ldi r20, 0x0D
    rcall uart_send
    ldi r20, 0x0A
    rcall uart_send
    ret

; ========================================================
; ROTINAS DE ARITMÉTICA FP16 (IEEE 754 Half Precision)
; ========================================================

; ------------------------------------------------------
; SOMA FP16: R16:R17 + R18:R19 -> R20:R21
; ------------------------------------------------------
fp16_add:
    push r22
    push r23
    push r24
    push r25
    push r26
    push r27
    push r28
    push r29
    push r30
    push r31

    ; Verifica se A é zero
    mov r22, r16
    andi r22, 0x7F
    or r22, r17
    brne fp16_add_a_nz
    mov r20, r18
    mov r21, r19
    rjmp fp16_add_done

fp16_add_a_nz:
    ; Verifica se B é zero
    mov r22, r18
    andi r22, 0x7F
    or r22, r19
    brne fp16_add_b_nz
    mov r20, r16
    mov r21, r17
    rjmp fp16_add_done

fp16_add_b_nz:
    ; Extrai expoente A em R23
    ldi r21, 0x7C
    mov r23, r16
    and r23, r21
    lsr r23
    lsr r23

    ; Extrai expoente B em R22
    mov r22, r18
    and r22, r21
    lsr r22
    lsr r22

    ; Compara expoentes
    cp r23, r22
    brlt fp16_add_exp_b_maior

    ; Caso: Exp A >= Exp B
    mov r31, r23        ; Expoente resultado
    sub r23, r22        ; Diferença de expoentes
    mov r24, r23        ; Contador de shifts

    ; Mantissa B será alinhada
    ldi r25, 0x03
    mov r26, r18
    and r26, r25
    ori r26, 0x04       ; Hidden bit
    mov r27, r19

    ; Mantissa A mantém posição
    mov r28, r16
    and r28, r25
    ori r28, 0x04       ; Hidden bit
    mov r29, r17
    rjmp fp16_add_align

fp16_add_exp_b_maior:
    mov r31, r22        ; Expoente resultado
    sub r22, r23        ; Diferença
    mov r24, r22        ; Contador

    ; Mantissa A será alinhada
    ldi r25, 0x03
    mov r26, r16
    and r26, r25
    ori r26, 0x04       ; Hidden bit
    mov r27, r17

    ; Mantissa B mantém posição
    mov r28, r18
    and r28, r25
    ori r28, 0x04       ; Hidden bit
    mov r29, r19

fp16_add_align:
    ; Alinha mantissa (shift right)
    tst r24
    breq fp16_add_sum

fp16_add_shift:
    lsr r26
    ror r27
    dec r24
    brne fp16_add_shift

fp16_add_sum:
    ; Soma mantissas
    add r27, r29
    adc r26, r28

    ; Verifica overflow (bit 3 setado)
    sbrs r26, 3
    rjmp fp16_add_norm

    ; Normaliza: shift right e incrementa expoente
    lsr r26
    ror r27
    inc r31

fp16_add_norm:
    ; Remove hidden bit
    andi r26, 0x03

    ; Empacota resultado
    mov r20, r31
    lsl r20
    lsl r20
    or r20, r26
    mov r21, r27

fp16_add_done:
    pop r31
    pop r30
    pop r29
    pop r28
    pop r27
    pop r26
    pop r25
    pop r24
    pop r23
    pop r22
    ret

; ------------------------------------------------------
; SUBTRAÇÃO FP16: R16:R17 - R18:R19 -> R20:R21
; ------------------------------------------------------
fp16_sub:
    push r2
    push r22
    push r23
    push r24
    push r25
    push r26
    push r27
    push r28
    push r29
    push r30
    push r31

    clr r30             ; Flag de sinal

    ; Compara magnitudes (ignora sinal)
    mov r22, r16
    andi r22, 0x7F
    mov r23, r18
    andi r23, 0x7F

    cp r17, r19
    cpc r22, r23
    brsh fp16_sub_no_swap

    ; Troca A <-> B
    ldi r30, 1          ; Resultado negativo
    mov r2, r16
    mov r16, r18
    mov r18, r2
    mov r2, r17
    mov r17, r19
    mov r19, r2

fp16_sub_no_swap:
    ; Extrai expoentes
    ldi r21, 0x7C
    mov r23, r16
    and r23, r21
    lsr r23
    lsr r23

    mov r22, r18
    and r22, r21
    lsr r22
    lsr r22

    ; Calcula shift
    mov r31, r23        ; Expoente resultado
    sub r23, r22
    mov r24, r23        ; Contador

    ; Prepara mantissas com hidden bit
    ldi r25, 0x03

    mov r26, r18        ; Mantissa menor
    and r26, r25
    ori r26, 0x04
    mov r27, r19

    mov r28, r16        ; Mantissa maior
    and r28, r25
    ori r28, 0x04
    mov r29, r17

    ; Alinha mantissa menor
    tst r24
    breq fp16_sub_do

fp16_sub_shift:
    lsr r26
    ror r27
    dec r24
    brne fp16_sub_shift

fp16_sub_do:
    ; Subtrai: maior - menor
    sub r29, r27
    sbc r28, r26

    ; Verifica zero
    mov r25, r28
    or r25, r29
    brne fp16_sub_norm

    ; Resultado zero
    clr r20
    clr r21
    rjmp fp16_sub_done

fp16_sub_norm:
    ; Normaliza (shift left até hidden bit em posição)
    sbrc r28, 2
    rjmp fp16_sub_pack

fp16_sub_norm_loop:
    lsl r29
    rol r28
    dec r31
    sbrs r28, 2
    rjmp fp16_sub_norm_loop

fp16_sub_pack:
    ; Remove hidden bit e empacota
    andi r28, 0x03

    mov r20, r31
    lsl r20
    lsl r20
    or r20, r28

    ; Aplica sinal
    sbrc r30, 0
    ori r20, 0x80

    mov r21, r29

fp16_sub_done:
    pop r31
    pop r30
    pop r29
    pop r28
    pop r27
    pop r26
    pop r25
    pop r24
    pop r23
    pop r22
    pop r2
    ret

; ------------------------------------------------------
; MULTIPLICAÇÃO FP16: R16:R17 * R18:R19 -> R20:R21
; ------------------------------------------------------
fp16_mul:
    push r22
    push r23
    push r24
    push r25
    push r26
    push r27
    push r28
    push r29
    push r30
    push r31

    ; Verifica zeros - usa trampolin para branch longo
    mov r22, r16
    andi r22, 0x7F
    or r22, r17
    brne fp16_mul_a_nz
    rjmp fp16_mul_zero       ; A é zero
fp16_mul_a_nz:

    mov r22, r18
    andi r22, 0x7F
    or r22, r19
    brne fp16_mul_b_nz
    rjmp fp16_mul_zero       ; B é zero
fp16_mul_b_nz:

    ; Calcula sinal (XOR)
    mov r30, r16
    eor r30, r18
    andi r30, 0x80

    ; Extrai e soma expoentes
    ldi r21, 0x7C

    mov r23, r16
    and r23, r21
    lsr r23
    lsr r23

    mov r22, r18
    and r22, r21
    lsr r22
    lsr r22

    add r23, r22
    subi r23, 15        ; Remove bias
    mov r31, r23        ; Expoente resultado

    ; Prepara mantissas com hidden bit
    ldi r25, 0x03

    mov r28, r16
    and r28, r25
    ori r28, 0x04
    mov r27, r17

    mov r24, r18
    and r24, r25
    ori r24, 0x04
    mov r22, r19

    ; Multiplicação de mantissas
    clr r29
    clr r26
    clr r25

    ; Low * Low
    mul r27, r22
    mov r25, r0
    mov r26, r1

    ; Low * High
    mul r27, r24
    add r26, r0
    adc r29, r1

    ; High * Low
    mul r28, r22
    add r26, r0
    adc r29, r1

    ; High * High
    mul r28, r24
    add r29, r0

    clr r1              ; Limpa R1

    ; Normaliza se necessário
    sbrs r29, 5
    rjmp fp16_mul_pack

    lsr r29
    ror r26
    inc r31

fp16_mul_pack:
    ; Empacota resultado
    mov r20, r31
    lsl r20
    lsl r20

    mov r24, r29
    lsr r24
    lsr r24
    andi r24, 0x03
    or r20, r24
    or r20, r30         ; Aplica sinal

    ; Byte baixo
    mov r21, r29
    lsl r21
    lsl r21
    lsl r21
    lsl r21
    lsl r21
    lsl r21

    mov r24, r26
    lsr r24
    lsr r24
    or r21, r24

    rjmp fp16_mul_done

fp16_mul_zero:
    clr r20
    clr r21

fp16_mul_done:
    pop r31
    pop r30
    pop r29
    pop r28
    pop r27
    pop r26
    pop r25
    pop r24
    pop r23
    pop r22
    ret

; ------------------------------------------------------
; DIVISÃO FP16: R16:R17 / R18:R19 -> R20:R21
; ------------------------------------------------------
fp16_div:
    push r22
    push r23
    push r24
    push r25
    push r26
    push r27
    push r28
    push r29
    push r30
    push r31

    ; Verifica divisor zero - usa trampolin
    mov r22, r18
    andi r22, 0x7F
    or r22, r19
    brne fp16_div_b_nz
    rjmp fp16_div_zero
fp16_div_b_nz:

    ; Verifica dividendo zero
    mov r22, r16
    andi r22, 0x7F
    or r22, r17
    brne fp16_div_a_nz
    rjmp fp16_div_zero
fp16_div_a_nz:

    ; Calcula sinal
    mov r30, r16
    eor r30, r18
    andi r30, 0x80

    ; Extrai expoentes
    ldi r21, 0x7C

    mov r23, r16
    and r23, r21
    lsr r23
    lsr r23

    mov r22, r18
    and r22, r21
    lsr r22
    lsr r22

    ; Calcula expoente: ExpA + 15 - ExpB
    ldi r24, 15
    add r23, r24
    sub r23, r22
    mov r31, r23

    ; Prepara mantissas
    ldi r25, 0x03

    mov r27, r16        ; Dividendo
    and r27, r25
    ori r27, 0x04
    mov r26, r17

    mov r29, r18        ; Divisor
    and r29, r25
    ori r29, 0x04
    mov r28, r19

    ; Loop de divisão (11 iterações)
    ldi r25, 11
    clr r20
    clr r21

fp16_div_loop:
    lsl r21
    rol r20

    cp r26, r28
    cpc r27, r29
    brlo fp16_div_no_sub

    sub r26, r28
    sbc r27, r29
    ori r21, 1

fp16_div_no_sub:
    lsl r26
    rol r27

    dec r25
    brne fp16_div_loop

    ; Normaliza
    sbrc r20, 2
    rjmp fp16_div_pack

fp16_div_norm:
    lsl r21
    rol r20
    dec r31
    sbrs r20, 2
    rjmp fp16_div_norm

fp16_div_pack:
    andi r20, 0x03

    mov r24, r31
    lsl r24
    lsl r24
    or r20, r24
    or r20, r30

    rjmp fp16_div_done

fp16_div_zero:
    clr r20
    clr r21

fp16_div_done:
    pop r31
    pop r30
    pop r29
    pop r28
    pop r27
    pop r26
    pop r25
    pop r24
    pop r23
    pop r22
    ret

; ------------------------------------------------------
; COMPARAÇÃO FP16: R16:R17 vs R18:R19
; Retorna em R20:R21: 0x3C00 (1.0) se true, 0x0000 se false
; R22 contém tipo de comparação:
;   0 = >, 1 = <, 2 = >=, 3 = <=, 4 = ==, 5 = !=
; ------------------------------------------------------
fp16_cmp:
    push r23
    push r24

    ; Compara bytes (considerando como unsigned para simplicidade)
    cp r17, r19
    cpc r16, r18

    ; Guarda flags
    in r23, SREG

    ; Resultado padrão: false
    clr r20
    clr r21

    ; Verifica tipo de comparação
    cpi r22, 0          ; >
    brne fp16_cmp_lt
    sbrc r23, 0         ; Se carry=0 e zero=0, então A > B
    rjmp fp16_cmp_done
    sbrc r23, 1
    rjmp fp16_cmp_done
    rjmp fp16_cmp_true

fp16_cmp_lt:
    cpi r22, 1          ; <
    brne fp16_cmp_ge
    sbrs r23, 0         ; Se carry=1, então A < B
    rjmp fp16_cmp_done
    rjmp fp16_cmp_true

fp16_cmp_ge:
    cpi r22, 2          ; >=
    brne fp16_cmp_le
    sbrc r23, 0         ; Se carry=0, então A >= B
    rjmp fp16_cmp_done
    rjmp fp16_cmp_true

fp16_cmp_le:
    cpi r22, 3          ; <=
    brne fp16_cmp_eq
    sbrs r23, 0         ; Se carry=1 ou zero=1
    rjmp fp16_cmp_chk_z
    rjmp fp16_cmp_true
fp16_cmp_chk_z:
    sbrs r23, 1
    rjmp fp16_cmp_done
    rjmp fp16_cmp_true

fp16_cmp_eq:
    cpi r22, 4          ; ==
    brne fp16_cmp_ne
    sbrs r23, 1         ; Se zero=1
    rjmp fp16_cmp_done
    rjmp fp16_cmp_true

fp16_cmp_ne:
    ; !=
    sbrc r23, 1         ; Se zero=0
    rjmp fp16_cmp_done
    rjmp fp16_cmp_true

fp16_cmp_true:
    ldi r20, 0x3C       ; 1.0 em FP16
    clr r21

fp16_cmp_done:
    pop r24
    pop r23
    ret

