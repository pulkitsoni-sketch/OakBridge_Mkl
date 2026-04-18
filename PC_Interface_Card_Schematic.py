"""
PC_Interface_Card_Schematic.py  —  OakBridge MkI (Rev V1, 31 Dec 2025)
=======================================================================
SKiDL script to regenerate the KiCad netlist and a grouped BOM for the
PC Interface Card.

Key ICs:
  U4  ESP32-S3-WROOM-1        (main MCU, Wi-Fi, BT)
  U3  MB85RS4MTYPN-GS-AWEWE1 (4 Mbit SPI FRAM)
  U2  TLV1117LV33DCYR         (3.3 V LDO regulator)
  U1  USBLC6-2SC6             (USB ESD protection)

Connectivity sourced from: PC_Interface_Card.net  (KiCad v9 export)
Component values sourced from: PC_Interface_Card.csv  (Digikey BOM)

IMPORTANT — explicit reference designators
------------------------------------------
Every instantiated part has its .ref set explicitly so that the generated
BOM reference strings match the original exactly.  Without this, SKiDL's
sequential auto-numbering re-orders references whenever the instantiation
order changes, producing value / reference mismatches.

Changes vs previous version
----------------------------
  * All .ref assignments are now explicit (fixes R/C numbering scramble).
  * All .value assignments are set on each instance, not only on templates
    (fixes generic "R" placeholders for ICs, connectors, diodes, etc.).
  * Capacitor values corrected: C1,C3,C13,C16 = 1u; remainder = 100n.
  * Resistor values corrected: R6,R7 = 5.1k; R17,R19,R22,R23,R26 = 33R;
    R27,R30,R34 = 68R; all others = 10k.
  * DNP components added: J4, J5 (GHR-11V-S), MD1 (display), MK1 (knob).
  * Spurious R8, R9 eliminated.

Usage:
    python PC_Interface_Card_Schematic.py
Outputs:
    PC_Interface_Card_skidl.net  — KiCad-compatible netlist
    PC_Interface_Card_BOM.csv   — grouped Bill of Materials
"""

import os
import csv
from collections import defaultdict

# ==========================================
# 1.  SETUP & PATHS  (edit to match your KiCad installation)
# ==========================================
app_symbols    = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols'
app_footprints = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'
user_config    = '/Users/user/Documents/KiCad/9.0'   # adjust if needed

os.environ['KICAD_SYMBOL_DIR']  = app_symbols
os.environ['KICAD6_SYMBOL_DIR'] = app_symbols
os.environ['KICAD7_SYMBOL_DIR'] = app_symbols
os.environ['KICAD8_SYMBOL_DIR'] = app_symbols
os.environ['KICAD9_SYMBOL_DIR'] = app_symbols

os.environ['KICAD_FOOTPRINT_DIR'] = app_footprints
os.environ['KICAD8_FOOTPRINT_DIR'] = app_footprints

from skidl import *   # noqa: E402  (must follow env-var setup)

lib_search_paths[KICAD].extend([app_symbols, user_config])
footprint_search_paths[KICAD].append(app_footprints)
set_default_tool(KICAD)


# ==========================================
# 2.  GLOBAL / POWER NETS
# ==========================================
gnd  = Net('GND')
vcc  = Net('VCC')    # 3.3 V regulated rail (output of U2)
vldo = Net('VLDO')   # LDO input rail (after fuse / bead / diode chain)
vusb = Net('VUSB')   # Raw USB 5 V (from J1 VBUS pins)


# ==========================================
# 3.  ALL SIGNAL NETS  (names match the .net file exactly)
# ==========================================
cc1, cc2     = Net('CC1'),       Net('CC2')
dp,  dn      = Net('D+'),        Net('D-')

clk_sd       = Net('CLK_SDMMC')
cmd_sd       = Net('CMD_SDMMC')
d0_sd        = Net('D0_SDMMC')
d1_sd        = Net('D1_SDMMC')
d2_sd        = Net('D2_SDMMC')
d3_sd        = Net('D3_SDMMC')

enc_a        = Net('ENC_A')
enc_b        = Net('ENC_B')
enc_sw       = Net('ENC_SW')

sclk         = Net('SCLK')
miso         = Net('MISO')
mosi         = Net('MOSI')
fram_cs      = Net('FRAM_CS')

cs_disp      = Net('CS_DISP')
dc_disp      = Net('DC_DISP')
rst_disp     = Net('RST_DISP')
pwm_disp     = Net('PWM_DISP')

sw_left      = Net('SW_LEFT')
sw_right     = Net('SW_RIGHT')
sw_up        = Net('SW_UP')
sw_dn        = Net('SW_DN')
sw_menu      = Net('SW_MENU')
sw_play      = Net('SW_PLAY')
sw_en        = Net('SW_EN')
sw_boot      = Net('SW_BOOT')

net_led1     = Net('Net-(LED1-Pad2)')
net_led2     = Net('Net-(LED2-Pad2)')
net_led3     = Net('Net-(LED3-Pad2)')
net_led4     = Net('Net-(LED4-Pad2)')
net_led5     = Net('Net-(LED5-Pad2)')

net_sw6_led  = Net('Net-(SW6-+)')
net_sw7_led  = Net('Net-(SW7-+)')
net_sw8_led  = Net('Net-(SW8-+)')

net_cr1_k    = Net('Net-(CR1-Pad2)')
net_f1_2     = Net('Net-(F1-Pad2)')

net_u3_reset = Net('Net-(U3-*RESET)')
net_u3_wp    = Net('Net-(U3-*WP)')

net_u4_io3   = Net('Net-(U4-IO3)')
net_u4_io45  = Net('Net-(U4-IO45)')
net_u4_io46  = Net('Net-(U4-IO46)')


# ==========================================
# 4.  HELPER FACTORIES
#     make_cap / make_res create a part, pin-1 connects to net_pos and
#     pin-2 to net_neg (defaulting to GND), then set an explicit ref.
#     Using helpers eliminates accidental auto-numbering and ensures
#     every component has the correct value string set on the instance.
# ==========================================
FP_C0603 = 'Capacitor_SMD:C_0603_1608Metric'
FP_R0603 = 'Resistor_SMD:R_0603_1608Metric'
VAL_1U   = '1u_16V_0603'
VAL_100N = '100n_16V_0603'


def make_cap(ref, value, net_pos, net_neg=None):
    """Create a capacitor with an explicit reference designator."""
    c = Part('Device', 'C', value=value, footprint=FP_C0603)
    c.ref = ref
    c[1] += net_pos
    c[2] += (net_neg if net_neg is not None else gnd)
    return c


def make_res(ref, value, net_1, net_2):
    """Create a resistor with an explicit reference designator."""
    r = Part('Device', 'R', value=value, footprint=FP_R0603)
    r.ref = ref
    r[1] += net_1
    r[2] += net_2
    return r


# ==========================================
# 5.  CAPACITORS  C1 – C19  (19 total)
#
#  1 µF  caps: C1, C3, C13, C16  (VCC bulk decoupling)
#  100 nF caps: everything else  (signal filter / LDO / VCC decoupling)
#
#  Source: PC_Interface_Card.csv rows "C1,C3,C13,C16" and
#          "C2,C4,C5,...,C19".
# ==========================================

# --- 1 µF VCC bulk decoupling ---
make_cap('C1',  VAL_1U,   vcc)
make_cap('C3',  VAL_1U,   vcc)
make_cap('C13', VAL_1U,   vcc)
make_cap('C16', VAL_1U,   vcc)

# --- 100 nF VCC decoupling ---
make_cap('C2',  VAL_100N, vcc)
make_cap('C15', VAL_100N, vcc)
make_cap('C18', VAL_100N, vcc)

# --- 100 nF VLDO input decoupling (C4) ---
# Net connection to vldo is set here; U2 is wired in section 8.
make_cap('C4', VAL_100N, vldo)

# Signal-filter caps C5-C12, C14, C17, C19 are created alongside their
# switches / encoder in sections 11 and 13-14, where their signal nets
# are already in scope, keeping wiring and component creation co-located.


# ==========================================
# 6.  POWER PATH
#     J1(VBUS) → F1 → FL1 → CR1(cathode → anode) → VLDO → U2 → VCC
# ==========================================

# --- J1: Amphenol GSB1C41110SSHR  USB-C receptacle ---
j1_t = Part('Device', 'R', dest=TEMPLATE)
j1_t.name, j1_t.ref_prefix = 'GSB1C41110SSHR', 'J'
j1_t.footprint = 'Footprint:AMPHENOL_GSB1C41110SSHR'
j1_t.pins = [
    Pin(num='A4_B9',  name='VBUS_A'),
    Pin(num='B4_A9',  name='VBUS_B'),
    Pin(num='A1_B12', name='GND_A'),
    Pin(num='B1_A12', name='GND_B'),
    Pin(num='A5',  name='CC1'),       Pin(num='B5',  name='CC2'),
    Pin(num='A6',  name='DP1'),       Pin(num='A7',  name='DN1'),
    Pin(num='B6',  name='DP2'),       Pin(num='B7',  name='DN2'),
    Pin(num='A8',  name='SBU1'),      Pin(num='B8',  name='SBU2'),
    Pin(num='SH1', name='SHIELD'),    Pin(num='SH2', name='SHIELD__1'),
    Pin(num='SH3', name='SHIELD__2'), Pin(num='SH4', name='SHIELD__3'),
]
j1 = j1_t()
j1.ref   = 'J1'
j1.value = 'GSB1C41110SSHR'
j1['VBUS_A', 'VBUS_B'] += vusb
j1['GND_A', 'GND_B', 'SHIELD', 'SHIELD__1', 'SHIELD__2', 'SHIELD__3'] += gnd
j1['CC1'] += cc1
j1['CC2'] += cc2
j1['DP1'] += dp
j1['DN1'] += dn
# DP2, DN2, SBU1, SBU2 → no-connect per schematic

# --- R6, R7: 5.1 kΩ USB CC pull-down resistors ---
make_res('R6', '5.1k_0.2W_0603', cc1, gnd)
make_res('R7', '5.1k_0.2W_0603', cc2, gnd)

# --- F1: Bel Fuse C1Q 1.5 A ---
f1_t = Part('Device', 'R', dest=TEMPLATE)
f1_t.name, f1_t.ref_prefix = 'C1Q_1.5', 'F'
f1_t.footprint = 'Footprint:C1_BEL-M'
f1_t.pins = [Pin(num='1', name='1'), Pin(num='2', name='2')]
f1 = f1_t()
f1.ref   = 'F1'
f1.value = 'C1Q 1.5'
f1['1'] += vusb
f1['2'] += net_f1_2

# --- FL1: Murata BLM18PG600SN1D ferrite bead ---
fl1_t = Part('Device', 'R', dest=TEMPLATE)
fl1_t.name, fl1_t.ref_prefix = 'BLM18PG600SN1D', 'FL'
fl1_t.footprint = 'Footprint:BEAD_BLM18PG_C1608X95N'
fl1_t.pins = [Pin(num='1', name='P1'), Pin(num='2', name='P2')]
fl1 = fl1_t()
fl1.ref   = 'FL1'
fl1.value = 'BLM18PG600SN1D'
fl1['P1'] += net_f1_2
fl1['P2'] += net_cr1_k

# --- CR1: Onsemi SS14 Schottky rectifier ---
cr1_t = Part('Device', 'R', dest=TEMPLATE)
cr1_t.name, cr1_t.ref_prefix = 'SS14', 'CR'
cr1_t.footprint = 'Footprint_Project_PC_Interface:SS14_CR_SMA_403AE_OSI-M'
cr1_t.pins = [Pin(num='1', name='A'), Pin(num='2', name='K')]
cr1 = cr1_t()
cr1.ref   = 'CR1'
cr1.value = 'SS14'
cr1['A'] += vldo
cr1['K'] += net_cr1_k

# --- U2: TI TLV1117LV33DCYR  3.3 V LDO (SOT-223-4) ---
u2_t = Part('Device', 'R', dest=TEMPLATE)
u2_t.name, u2_t.ref_prefix = 'TLV1117LV33DCYR', 'U'
u2_t.footprint = 'Footprint:VREG_TLV1117LV33DCYR'
u2_t.pins = [
    Pin(num='1', name='GND'),
    Pin(num='2', name='OUT_2'),
    Pin(num='3', name='IN'),
    Pin(num='4', name='OUT_4'),
]
u2 = u2_t()
u2.ref   = 'U2'
u2.value = 'TLV1117LV33DCYR'
u2['GND']            += gnd
u2['IN']             += vldo
u2['OUT_2', 'OUT_4'] += vcc


# ==========================================
# 7.  USB ESD PROTECTION: STMicro USBLC6-2SC6  (U1, SOT-23-6)
# ==========================================
u1_t = Part('Device', 'R', dest=TEMPLATE)
u1_t.name, u1_t.ref_prefix = 'USBLC6-2SC6', 'U'
u1_t.footprint = 'Package_TO_SOT_SMD:SOT-23-6'
u1_t.pins = [
    Pin(num='1', name='IO1_A'),   # D+ side A
    Pin(num='6', name='IO1_B'),   # D+ side B
    Pin(num='3', name='IO2_A'),   # D- side A
    Pin(num='4', name='IO2_B'),   # D- side B
    Pin(num='2', name='GND'),
    Pin(num='5', name='VBUS'),
]
u1 = u1_t()
u1.ref   = 'U1'
u1.value = 'USBLC6-2SC6'
u1['IO1_A', 'IO1_B'] += dp
u1['IO2_A', 'IO2_B'] += dn
u1['GND']  += gnd
u1['VBUS'] += vusb


# ==========================================
# 8.  ESP32-S3-WROOM-1  (U4) — all 41 pins
# ==========================================
u4_t = Part('Device', 'R', dest=TEMPLATE)
u4_t.name, u4_t.ref_prefix = 'ESP32-S3-WROOM-1', 'U'
u4_t.footprint = 'RF_Module:ESP32-S3-WROOM-1'
u4_t.pins = [
    Pin(num='1',  name='GND'),    Pin(num='2',  name='3V3'),
    Pin(num='3',  name='EN'),     Pin(num='4',  name='IO4'),
    Pin(num='5',  name='IO5'),    Pin(num='6',  name='IO6'),
    Pin(num='7',  name='IO7'),    Pin(num='8',  name='IO15'),
    Pin(num='9',  name='IO16'),   Pin(num='10', name='IO17'),
    Pin(num='11', name='IO18'),   Pin(num='12', name='IO8'),
    Pin(num='13', name='USB_D-'), Pin(num='14', name='USB_D+'),
    Pin(num='15', name='IO3'),    Pin(num='16', name='IO46'),
    Pin(num='17', name='IO9'),    Pin(num='18', name='IO10'),
    Pin(num='19', name='IO11'),   Pin(num='20', name='IO12'),
    Pin(num='21', name='IO13'),   Pin(num='22', name='IO14'),
    Pin(num='23', name='IO21'),   Pin(num='24', name='IO47'),
    Pin(num='25', name='IO48'),   Pin(num='26', name='IO45'),
    Pin(num='27', name='IO0'),    Pin(num='28', name='IO35'),
    Pin(num='29', name='IO36'),   Pin(num='30', name='IO37'),
    Pin(num='31', name='IO38'),   Pin(num='32', name='IO39'),
    Pin(num='33', name='IO40'),   Pin(num='34', name='IO41'),
    Pin(num='35', name='IO42'),   Pin(num='36', name='RXD0'),
    Pin(num='37', name='TXD0'),   Pin(num='38', name='IO2'),
    Pin(num='39', name='IO1'),    Pin(num='40', name='GND_40'),
    Pin(num='41', name='GND_41'),
]
u4 = u4_t()
u4.ref   = 'U4'
u4.value = 'ESP32-S3-WROOM-1'

u4['GND', 'GND_40', 'GND_41'] += gnd
u4['3V3'] += vcc

u4['USB_D+'] += dp
u4['USB_D-'] += dn

# SD / MMC 4-bit
u4['IO39'] += clk_sd
u4['IO38'] += cmd_sd
u4['IO40'] += d0_sd
u4['IO41'] += d1_sd
u4['IO42'] += d2_sd
u4['IO47'] += d3_sd

# Rotary encoder
u4['IO4'] += enc_a
u4['IO5'] += enc_b
u4['IO6'] += enc_sw

# SPI (shared by FRAM and display)
u4['IO12'] += sclk
u4['IO13'] += miso
u4['IO11'] += mosi
u4['IO14'] += fram_cs

# Display
u4['IO10'] += cs_disp
u4['IO9']  += dc_disp
u4['IO8']  += rst_disp
u4['IO48'] += pwm_disp

# Buttons
u4['IO17'] += sw_left
u4['IO16'] += sw_up
u4['TXD0'] += sw_right
u4['IO18'] += sw_dn
u4['IO15'] += sw_menu
u4['RXD0'] += sw_play
u4['EN']   += sw_en
u4['IO0']  += sw_boot

# Strapping pins
u4['IO3']  += net_u4_io3
u4['IO46'] += net_u4_io46
u4['IO45'] += net_u4_io45

# Strapping-pin pull-down resistors  (pin1 = GND per .net file)
make_res('R28', '10k_0.2W_0603', gnd, net_u4_io3)
make_res('R31', '10k_0.2W_0603', gnd, net_u4_io46)
make_res('R32', '10k_0.2W_0603', gnd, net_u4_io45)


# ==========================================
# 9.  FRAM: Ramxeed MB85RS4MTYPN-GS-AWEWE1  (U3)
# ==========================================
u3_t = Part('Device', 'R', dest=TEMPLATE)
u3_t.name, u3_t.ref_prefix = 'MB85RS4MTYPN-GS-AWEWE1', 'U'
u3_t.footprint = 'Footprint:DFN8_FUJ-M'
u3_t.pins = [
    Pin(num='1', name='*CS'),    Pin(num='2', name='SO'),
    Pin(num='3', name='*WP'),    Pin(num='4', name='VSS'),
    Pin(num='5', name='SI'),     Pin(num='6', name='SCK'),
    Pin(num='7', name='*RESET'), Pin(num='8', name='VDD'),
    Pin(num='9', name='VSS2'),   # exposed pad / second GND
]
u3 = u3_t()
u3.ref   = 'U3'
u3.value = 'MB85RS4MTYPN-GS-AWEWE1'
u3['*CS']         += fram_cs
u3['SO']          += miso
u3['SI']          += mosi
u3['SCK']         += sclk
u3['VSS', 'VSS2'] += gnd
u3['VDD']         += vcc
u3['*WP']         += net_u3_wp
u3['*RESET']      += net_u3_reset

# R16: pull *WP HIGH (write-protect disabled)
# R24: pull *RESET to GND via 10 kΩ (per .net file — pin1=GND, pin2=*RESET)
make_res('R16', '10k_0.2W_0603', net_u3_wp,    vcc)
make_res('R24', '10k_0.2W_0603', gnd,          net_u3_reset)


# ==========================================
# 10.  microSD CONNECTOR: Hirose DM3BT-DSF-PEJS  (J2)
# ==========================================
j2_t = Part('Device', 'R', dest=TEMPLATE)
j2_t.name, j2_t.ref_prefix = 'DM3BT-DSF-PEJS', 'J'
j2_t.footprint = 'Footprint_Project_PC_Interface:HRS_DM3BT-DSF-PEJS'
j2_t.pins = [
    Pin(num='1',    name='DAT2'),       Pin(num='2',    name='DAT3/CD'),
    Pin(num='3',    name='CMD'),        Pin(num='4',    name='VDD'),
    Pin(num='5',    name='CLK'),        Pin(num='6',    name='VSS'),
    Pin(num='7',    name='DAT0'),       Pin(num='8',    name='DAT1'),
    Pin(num='S1',   name='SHIELD'),     Pin(num='S2',   name='SHIELD__1'),
    Pin(num='S3',   name='SHIELD__2'),  Pin(num='S4',   name='SHIELD__3'),
    Pin(num='SW-A', name='SW-A'),       Pin(num='SW-B', name='SW-B'),
]
j2 = j2_t()
j2.ref   = 'J2'
j2.value = 'DM3BT-DSF-PEJS'
j2['VDD'] += vcc
j2['VSS'] += gnd
j2['SHIELD', 'SHIELD__1', 'SHIELD__2', 'SHIELD__3'] += gnd
j2['CLK']     += clk_sd
j2['CMD']     += cmd_sd
j2['DAT0']    += d0_sd
j2['DAT1']    += d1_sd
j2['DAT2']    += d2_sd
j2['DAT3/CD'] += d3_sd
# SW-A, SW-B → no-connect

# SD DAT / CMD pull-up resistors (R1 – R5, 10 kΩ)
make_res('R1', '10k_0.2W_0603', d0_sd,  vcc)
make_res('R2', '10k_0.2W_0603', d1_sd,  vcc)
make_res('R3', '10k_0.2W_0603', d2_sd,  vcc)
make_res('R4', '10k_0.2W_0603', d3_sd,  vcc)
make_res('R5', '10k_0.2W_0603', cmd_sd, vcc)


# ==========================================
# 11.  DISPLAY / SPI HEADER: JST BM11B-GHS-TBT  (J3)  Conn_01x13
# ==========================================
j3_t = Part('Device', 'R', dest=TEMPLATE)
j3_t.name, j3_t.ref_prefix = 'BM11B-GHS-TBT', 'J'
j3_t.footprint = 'Footprint_Project_PC_Interface:CONN11_BM11B-GHS-TBTLFSNN_JST'
j3_t.pins = [Pin(num=str(i), name=f'Pin_{i}') for i in range(1, 14)]
j3 = j3_t()
j3.ref   = 'J3'
j3.value = 'BM11B-GHS-TBT'
j3['Pin_1']  += vcc
j3['Pin_2']  += gnd
j3['Pin_3']  += miso
j3['Pin_4']  += mosi
j3['Pin_5']  += sclk
j3['Pin_6']  += cs_disp
j3['Pin_7']  += dc_disp
j3['Pin_8']  += rst_disp
j3['Pin_9']  += pwm_disp
j3['Pin_12'] += gnd
j3['Pin_13'] += gnd
# Pin_10, Pin_11 → no-connect

# RST_DISP pull-up (R10, 10 kΩ)
make_res('R10', '10k_0.2W_0603', rst_disp, vcc)


# ==========================================
# 12.  DNP CABLE CONNECTORS  J4, J5: JST GHR-11V-S
#      Cable-side mates for J3.  DNP / Excluded from board.
#      No net connections — BOM line items only.
# ==========================================
ghr_t = Part('Device', 'R', dest=TEMPLATE)
ghr_t.name, ghr_t.ref_prefix = 'GHR-11V-S', 'J'
ghr_t.footprint = ''
ghr_t.pins = [Pin(num=str(i), name=f'Pin_{i}') for i in range(1, 12)]

j4 = ghr_t()
j4.ref   = 'J4'
j4.value = 'GHR-11V-S'

j5 = ghr_t()
j5.ref   = 'J5'
j5.value = 'GHR-11V-S'


# ==========================================
# 13.  ROTARY ENCODER: Same Sky ACZ11BR1E-15KQA1-12C  (MT1)
#      Quadrature incremental encoder with integrated push-switch.
#
#      Pin map (from .net libpart):
#        A, B   — quadrature outputs
#        C      — encoder common  → GND
#        D      — push-switch signal
#        E      — push-switch common → GND
#        SH1/2  — shield           → GND
# ==========================================
mt1_t = Part('Device', 'R', dest=TEMPLATE)
mt1_t.name, mt1_t.ref_prefix = 'ACZ11BR1E-15KQA1-12C', 'MT'
mt1_t.footprint = 'Footprint:XDCR_ACZ11BR1E-15KQA1-12C'
mt1_t.pins = [
    Pin(num='A',   name='A'),
    Pin(num='B',   name='B'),
    Pin(num='C',   name='C'),
    Pin(num='D',   name='D'),
    Pin(num='E',   name='E'),
    Pin(num='SH1', name='SHIELD'),
    Pin(num='SH2', name='SHIELD__1'),
]
mt1 = mt1_t()
mt1.ref   = 'MT1'
mt1.value = 'ACZ11BR1E-15KQA1-12C'
mt1['A'] += enc_a
mt1['B'] += enc_b
mt1['C'] += gnd
mt1['D'] += enc_sw
mt1['E'] += gnd
mt1['SHIELD', 'SHIELD__1'] += gnd

# Pull-up resistors (R18=ENC_A, R20=ENC_B, R13=ENC_SW)
make_res('R18', '10k_0.2W_0603', enc_a,  vcc)
make_res('R20', '10k_0.2W_0603', enc_b,  vcc)
make_res('R13', '10k_0.2W_0603', enc_sw, vcc)

# 100 nF filter capacitors (C10, C11, C7)
make_cap('C10', VAL_100N, enc_a)
make_cap('C11', VAL_100N, enc_b)
make_cap('C7',  VAL_100N, enc_sw)


# ==========================================
# 14.  CHERRY MX KEY SWITCHES  SW1 – SW5
#      Wiring: signal net pulled to VCC via 10 kΩ + 100 nF filter to GND.
#      When pressed, switch shorts signal to GND (pin 2).
# ==========================================
cherry_t = Part('Device', 'R', dest=TEMPLATE)
cherry_t.name, cherry_t.ref_prefix = 'CherryMX', 'SW'
cherry_t.footprint = 'CherryMX_PCB:CherryMX_1.00u_PCB'
cherry_t.pins = [Pin(num='1', name='SIG'), Pin(num='2', name='COM')]

# (SW_ref, signal_net, R_ref, C_ref)
cherry_cfg = [
    ('SW1', sw_left,  'R11', 'C5'),
    ('SW2', sw_up,    'R12', 'C6'),
    ('SW3', sw_right, 'R14', 'C8'),
    ('SW4', sw_dn,    'R15', 'C9'),
    ('SW5', sw_menu,  'R21', 'C12'),
]
for sw_ref, sig, r_ref, c_ref in cherry_cfg:
    sw = cherry_t()
    sw.ref   = sw_ref
    sw.value = 'CherryMX'
    sw['SIG'] += sig
    sw['COM'] += gnd
    make_res(r_ref, '10k_0.2W_0603', sig, vcc)
    make_cap(c_ref, VAL_100N, sig)


# ==========================================
# 15.  ILLUMINATED TACTILE SWITCHES  SW6 – SW8
#      Part: E-Switch TL1240YQ2JBLK  (SPST-NO + integral LED, THT)
#
#      Pin map (from .net libpart):
#        1, 2   — switch contact A  → signal net
#        3, 4   — switch contact B  → GND  (shorts signal to GND when pressed)
#        5  (+) — LED anode
#        6  (-) — LED cathode       → GND
#
#      LED: VCC → R_led (68 Ω) → LED+.
#      Signal: pulled to VCC via R_pu (10 kΩ) + C_filter (100 nF).
# ==========================================
tact_t = Part('Device', 'R', dest=TEMPLATE)
tact_t.name, tact_t.ref_prefix = 'TL1240YQ2JBLK', 'SW'
tact_t.footprint = 'Footprint:TL1240YQ'
tact_t.pins = [
    Pin(num='1', name='SW_A1'), Pin(num='2', name='SW_A2'),
    Pin(num='3', name='SW_B1'), Pin(num='4', name='SW_B2'),
    Pin(num='5', name='+'),     Pin(num='6', name='-'),
]

# --- SW6: SW_PLAY  (U4 RXD0) ---
sw6 = tact_t()
sw6.ref   = 'SW6'
sw6.value = 'TL1240YQ2JBLK'
sw6['SW_A1', 'SW_A2'] += sw_play
sw6['SW_B1', 'SW_B2', '-'] += gnd
sw6['+'] += net_sw6_led
make_res('R27', '68R_0.2W_0603',  net_sw6_led, vcc)   # LED series resistor
make_res('R25', '10k_0.2W_0603',  sw_play,     vcc)   # signal pull-up
make_cap('C14', VAL_100N, sw_play)                     # signal filter cap

# --- SW7: SW_EN  (U4 EN / reset) ---
sw7 = tact_t()
sw7.ref   = 'SW7'
sw7.value = 'TL1240YQ2JBLK'
sw7['SW_A1', 'SW_A2'] += sw_en
sw7['SW_B1', 'SW_B2', '-'] += gnd
sw7['+'] += net_sw7_led
make_res('R30', '68R_0.2W_0603',  net_sw7_led, vcc)
make_res('R29', '10k_0.2W_0603',  sw_en,       vcc)
make_cap('C17', VAL_100N, sw_en)

# --- SW8: SW_BOOT  (U4 IO0 / boot strapping) ---
sw8 = tact_t()
sw8.ref   = 'SW8'
sw8.value = 'TL1240YQ2JBLK'
sw8['SW_A1', 'SW_A2'] += sw_boot
sw8['SW_B1', 'SW_B2', '-'] += gnd
sw8['+'] += net_sw8_led
make_res('R34', '68R_0.2W_0603',  net_sw8_led, vcc)
make_res('R33', '10k_0.2W_0603',  sw_boot,     vcc)
make_cap('C19', VAL_100N, sw_boot)


# ==========================================
# 16.  STATUS LEDs  LED1 – LED5  (Cree JE2835ARY, 3528, blue 455 nm)
#
#      Circuit: VCC → R_series (33 Ω) → LED anode
#               LED cathode → GND
# ==========================================
led_t = Part('Device', 'R', dest=TEMPLATE)
led_t.name, led_t.ref_prefix = 'LED_Cree_JE2835', 'LED'
led_t.footprint = 'Footprint:LED_JE2835_CRW-M'
led_t.pins = [Pin(num='1', name='K'), Pin(num='2', name='A')]

# (LED_ref, anode_net, series_R_ref)
led_cfg = [
    ('LED1', net_led1, 'R17'),
    ('LED2', net_led2, 'R19'),
    ('LED3', net_led3, 'R22'),
    ('LED4', net_led4, 'R23'),
    ('LED5', net_led5, 'R26'),
]
for led_ref, anode_net, r_ref in led_cfg:
    led = led_t()
    led.ref   = led_ref
    led.value = 'LED_Cree_JE2835'
    led['K'] += gnd
    led['A'] += anode_net
    make_res(r_ref, '33R_0.2W_0603', anode_net, vcc)


# ==========================================
# 17.  DNP MECHANICAL / DISPLAY ITEMS
#      Marked DNP / Excluded from board in original BOM.
#      Instantiated here so the generated BOM row counts match.
# ==========================================

# MD1: WaveShare 3.5" RPi LCD (G) — display module
md1_t = Part('Device', 'R', dest=TEMPLATE)
md1_t.name, md1_t.ref_prefix = 'WaveShare_3.5in_RPi_LCD', 'MD'
md1_t.footprint = ''
md1_t.pins = [Pin(num='1', name='NC')]
md1 = md1_t()
md1.ref   = 'MD1'
md1.value = 'WaveShare 3.5" RPi LCD (G)'

# MK1: Kilo International OEDNI-75-4-7 encoder knob
mk1_t = Part('Device', 'R', dest=TEMPLATE)
mk1_t.name, mk1_t.ref_prefix = 'OEDNI-75-4-7', 'MK'
mk1_t.footprint = ''
mk1_t.pins = [Pin(num='1', name='NC')]
mk1 = mk1_t()
mk1.ref   = 'MK1'
mk1.value = 'OEDNI-75-4-7'


# ==========================================
# 18.  OUTPUT: KiCad netlist  +  CSV BOM
# ==========================================
def generate_csv_bom(filename='PC_Interface_Card_BOM.csv'):
    """
    Walk every instantiated part, group by (name, value, footprint),
    sort references, and write a Digikey-style BOM.
    """
    bom_groups = defaultdict(list)

    for part in default_circuit.parts:  # type: ignore
        is_template = getattr(part, 'dest', None) == TEMPLATE  # type: ignore
        has_no_ref  = not getattr(part, 'ref',  None)
        if is_template or has_no_ref:
            continue

        key = (
            getattr(part, 'name',      ''),
            getattr(part, 'value',     ''),
            getattr(part, 'footprint', ''),
        )
        bom_groups[key].append(part.ref)

    with open(filename, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Quantity', 'Reference(s)', 'Value',
                         'Part Name', 'Footprint'])
        for (name, value, footprint), refs in sorted(bom_groups.items()):
            refs.sort()
            writer.writerow([len(refs), ', '.join(refs), value,
                             name, footprint])

    print(f'✅  BOM   saved  →  {filename}')


generate_netlist(filename='PC_Interface_Card_skidl.net')
print('✅  Netlist saved  →  PC_Interface_Card_skidl.net')
generate_csv_bom(filename='PC_Interface_Card_BOM.csv')