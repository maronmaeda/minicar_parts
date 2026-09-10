# -*- coding: utf-8 -*-
"""
FaBo JetRacer Kit Race Edition  ×  Intel RealSense D455
==========================================================
既存の「タワー」(タワー.FCStd の Body) の上面 Z=100 にドッキングする、
2つの独立したボディを生成する。

  ADJUSTER  ... ピッチ角調整機構 (ヨーク = ベース板 + 頬板2枚 + 円弧長穴)
  CAM_MOUNT ... D455 固定治具 (背面プレート + 上端リブ + シェルフ + クランプタブ)

どちらも「そのまま1ボディで印刷 → 後からボルト2本でドッキング」できる形状。
サポート不要 (ADJUSTER=ベース底面をベッドに / CAM_MOUNT=背面プレート裏面をベッドに)。
CAM_MOUNT の突起 (タブ・シェルフ・リブ) はすべて +Y 側に揃えてあるので、
背面プレートを寝かせれば全部が上向きに立ち上がる。

------------------------------------------------------------------
rev.3 で追加したこと: 締結部品 (ボルト・ワッシャ・ナット) の作り込み
------------------------------------------------------------------
ねじの実物がまだ決まっていないので、**FASTENERS の1表だけ書き換えれば
部品の大きさが追従する**構造にした。ワッシャ外径を変えれば頬板の Y 幅も
ベース板の奥行も、カメラの高さ CAM_Z0 まで自動で計算し直される。

  ワッシャ座面   : 全ピッチ角でワッシャ外周が母材に載るように頬板寸法を逆算
  頭 / ナット    : 実形状の参照ソリッドを置き、他部品との干渉を毎回チェック
  工具           : ソケット / レンチの回転径ぶんの空間も参照に含める

寸法を変えたら必ず末尾の検証出力を見ること。NG があればそこに出る。

------------------------------------------------------------------
rev.2 で直したこと
------------------------------------------------------------------
[BUG] 回転軸穴とクランプ穴を XZ 平面のスケッチに描いていたため、穴の軸方向が
      Y (前後) になっていた。ボルトは X (左右) から入るので機能しない穴だった。
      -> YZ 平面のスケッチに移し、X 方向に貫通させた。
[改良] タブが板厚 6 mm しかなく、頬板が掴むのが 6 mm 幅の板コバだけだった。
      面圧 9.7 MPa は樹脂のクリープ限界ちょうどで予圧が抜ける。
      -> 14 mm 厚のボスにして 4.0 MPa に。
[改良] 回転軸をタブ厚の中心に移し、カメラ重心との腕を短縮。

------------------------------------------------------------------
D455 の与件 (Intel データシート 337029-017 / 図 MD0645501 Sheet 3/3 実読値)
------------------------------------------------------------------
  外形            124 (W) x 29 (H) x 26 (D) mm
  背面 M4 x 2     ピッチ 95 mm / 高さは背面の上下中心 (底面から 14.5 mm)
                  ねじ込み深さ最大 4 mm / 推奨トルク 0.4 N・m
  底面 1/4-20     X中心 (光軸中心線上)、ねじ込み深さ最大 9 mm
  USB-C           ※背面ではなく「底面」。X中心から約 46.5 mm
  質量            116 g

再実行すると ADJUSTER / CAM_MOUNT / 参照ソリッドを作り直す (冪等)。
スケッチはすべて完全拘束された状態で残るので、GUI からの寸法編集も可能。
"""

import math
import FreeCAD as App
import Part
import Sketcher

try:
    import FreeCADGui as Gui
    HAS_GUI = App.GuiUp
except Exception:
    HAS_GUI = False

S20 = math.sin  # 読みやすさ用

# =====================================================================
# PARAMETERS  (すべて mm / deg)
# =====================================================================

DOC_NAME = "Unnamed"          # ラベル「タワー」のドキュメント内部名

# ---------------------------------------------------------------------
# ★ 締結部品の諸元 — 実物のねじを決めたら「ここだけ」書き換える
# ---------------------------------------------------------------------
#   clear      : バカ穴の径
#   washer_od  : 平ワッシャ外径   washer_t : ワッシャ厚
#   head_d     : ボルト頭の径     head_h   : ボルト頭の高さ
#   nut_af     : ナット二面幅     nut_h    : ナット高さ (ナイロンナットは背高)
#   tool_d     : 工具(ソケット/めがね)の回転径。0 なら六角レンチで済むとみなす
#   torque     : 締付トルク [N.m]。予圧 F = torque / (0.2 * d) の計算に使う
#   nom_d      : 呼び径
# ねじ込み深さ (めねじ側に入る長さ)。干渉判定でここは「意図した貫入」として扱う
ENGAGE = {'cam': 4.0, 'base': 6.0}      # cam: D455 は最大 4 / base: インサート内
FASTENERS = {
    # タワー <-> ADJUSTER (4本)。タワー側は M3 熱圧入インサート
    #   タワーが 50x24 に縮んだのでワッシャは OD9 に落とす。
    #   OD9 で 0.35 N.m だと座面 10.7 MPa でクリープ限界超え -> 0.30 N.m にする
    'base':  dict(label='M3x12',  nom_d=3.0, clear=3.4,
                  washer_od=9.0,  washer_t=0.8, head_d=5.5, head_h=3.0,
                  nut_af=0.0,     nut_h=0.0,    tool_d=0.0,  torque=0.30),
    # ADJUSTER <-> CAM_MOUNT 回転軸 (1本、貫通ナット止め)
    #   OD14 は 24 mm 奥行に収まらないので OD12。座面を守るためトルクは 0.7 N.m
    'pivot': dict(label='M4x40',  nom_d=4.0, clear=4.5,
                  washer_od=12.0, washer_t=1.0, head_d=7.0, head_h=4.0,
                  nut_af=7.0,     nut_h=5.0,    tool_d=14.0, torque=0.70),
    # ADJUSTER <-> CAM_MOUNT クランプ (1本、円弧長穴を通る)
    'clamp': dict(label='M4x40',  nom_d=4.0, clear=4.5,
                  washer_od=12.0, washer_t=1.0, head_d=7.0, head_h=4.0,
                  nut_af=7.0,     nut_h=5.0,    tool_d=14.0, torque=0.70),
    # CAM_MOUNT <-> D455 背面 (2本、カメラ側のめねじにねじ込む)
    #   ねじ込み深さ最大 4 mm。プレート厚 + ワッシャ厚 + 4 が使える最大長。
    'cam':   dict(label='M4x10',  nom_d=4.0, clear=4.5,
                  washer_od=12.0, washer_t=1.0, head_d=7.0, head_h=4.0,
                  nut_af=0.0,     nut_h=0.0,    tool_d=0.0,  torque=0.40),
}
SEAT_MARGIN = 1.5             # ワッシャ外周から部品の縁までの最小残り
SWING_CLEAR = 3.0             # ピッチ回転時のすきま
BASE_CLEAR = 2.0              # タブ下端とベース板上面のすきま
MU = 0.35                     # PETG 同士の静摩擦係数 (控えめな値)
CRASH_G = 64.0                # 引き継ぎ書 3.6 節のクラッシュ加速度
CREEP_LIMIT = 10.0            # 樹脂の座面圧の上限 [MPa]
# 全体高さの上限 (タワー底面基準)。
#   当初 160 -> 「車体・バンパーが画角に入るので少し超えてもよい」で 165
#   -> 「むしろ低いほうが問題」との判断で 170 に緩めた。
#   高さを上げると固有振動数は下がる (f ∝ L^-1.5) ので、上限を外すのではなく
#   ここに書いた値で頭打ちにしておくこと。
MAX_TOTAL_H = 170.0

# --- 既存タワー (ユーザーが実測して 01_TOWER.FCStd で確定させた寸法) --
# parts/01_TOWER.FCStd の Body 実測値と一致させること
TOWER_W = 50.0                # X 幅
TOWER_D = 24.0                # Y 奥行
TOWER_TOP_Z = 70.0            # 上面の Z

# --- タワー上面の M3 熱圧入インサート ---------------------------------
INSERT_D = 4.2                # インサート下穴径 (M3 用 OD4.0-4.6 想定)
INSERT_DEPTH = 8.0

# --- ADJUSTER : ベース板 ----------------------------------------------
# ★ ベース板厚 = 全体高さの調整つまみ。
#   「車体・バンパーが画角に入る」対策で光軸を上げる要求があり、ここで稼ぐ。
#   ヨークを伸ばして上げるより、ベースを厚くして上げるほうが片持ち長が短くなり
#   固有振動数が落ちない (6->17 で頬板の f_n は 168 -> 225 Hz)。
#   一体版ではここはタワーと連続した中実材になる。
#   分割版のままここを厚くする場合は M3 の長さを BASE_T + 6 mm 以上にすること。
# PIV_Y を 1.5 -> 0 にするとピッチが ±20deg に広がり、そのぶん
# 回転時のクリアランス確保でカメラが 2 mm 上がる。全体高さを 170 に保つため
# 台座を 21.0 -> 19.0 に戻して相殺している (光軸 147.4 は変わらない)。
BASE_T = 19.0                 # 6.0 が最小。全体高さ = BASE_T + 150.9
BASE_Z0 = TOWER_TOP_Z
BASE_Z1 = BASE_Z0 + BASE_T

# --- クランプ (円弧長穴) ----------------------------------------------
# 円弧は必ず「回転軸の真上」。クランプ穴はタブ側では固定位置なので、
# タブが厚みを持っている方向 = 真上 にしか置けない。
# 回転軸 PIV_Y / PIV_Z、および実際の ARC_R / ARC_SPAN は DERIVED で計算する。
#
# ★ ARC_R は「回転軸ボルトとクランプボルトのワッシャが当たらない距離」が下限。
#   rev.4 で 8.5 にしたらワッシャ (OD12 = 半径6) 同士が 40.85 mm3 食い込んでいた。
#   下限 = 回転軸座金R + クランプ座金R + FASTENER_CLEAR
ARC_R_WANT = 13.0             # 希望する腕長。下限を下回る値を書いても下限まで押し上げる
ARC_SPAN_WANT = 20.0          # 希望する振り角 ±deg。ベース奥行に収まる範囲まで自動で落とす
ARC_SPAN_MIN = 10.0           # これを下回ったら設計として NG にする
FASTENER_CLEAR = 1.0          # 締結部品どうしの最小すきま
# ★ 回転軸の Y。頬板 (Y -12..12) の中心は 0。
#   rev.9 まで PIV_Y は -PLATE_T/2 + TAB_T/2 の従属値で、たまたま 1.5 になっていた。
#   パラメータに昇格させたとき配置を変えないよう 1.5 を据え置いたが、
#   これは設計意図ではなく名残。0 にすると
#     - 回転軸と円弧長穴が頬板の中心に乗る (見た目も左右対称)
#     - 円弧の Y 振れ余裕が 3.0 -> 4.5 mm に増え、ピッチが ±13 -> ±20deg に戻る
#   代償はカメラが 1.5 mm 後退することだけ (モーメントはむしろ減る)。
PIV_Y_WANT = 0.0              # 回転軸の Y。小さいほどピッチ範囲が広がる

# --- ADJUSTER : 頬板 (cheek) / CAM_MOUNT : クランプタブ ---------------
# タワーが 50 x 24 に縮んだので rev.3 から詰めた。効いている制約は 2 本:
#   ベース幅 2*(CHEEK_XO + M3座金R + 余白) <= TOWER_W   -> TAB_W と CHEEK_T
#   ベース奥行 2*(PIV_Y + ARC_R*sinSPAN + 座金R + 余白) <= TOWER_D
#                                          -> TAB_T (PIV_Y = -PLATE_T/2 + TAB_T/2) と ARC_R
# タブ首部の断面係数 = TAB_W * TAB_T^2 / 6。
# TAB_T はピッチ範囲に縛られて増やせない (PIV_Y = -PLATE_T/2 + TAB_T/2 が
# 円弧の Y 振れを圧迫するため) ので、剛性を上げるレバーは TAB_W しかない。
#   TAB_W 14 -> 24 で断面係数 189 -> 324 mm3、層間応力 11.4 -> 6.6 MPa
# ただし分割版では頬板が太るぶん M3 の座金が横に逃げられなくなる (下の FIX_FITS)。
TAB_W = 24.0                  # タブの X 幅
# ★ TAB_T (タブの Y 厚) は頬板が掴む面の幅。厚いほど面圧が下がり首も強い。
#   rev.8 までは PIV_Y = -PLATE_T/2 + TAB_T/2 という従属値だったため、
#   TAB_T を増やすと回転軸が前に出てピッチ範囲を食いつぶしていた
#   (TAB_T=12 で ±6.6deg まで落ちる)。
#   rev.9 で PIV_Y をパラメータにし、プレートの Y 位置のほうをずらして
#   吸収するようにしたので、TAB_T はピッチ範囲と独立に増やせる。
TAB_T = 14.0                  # タブの Y 厚。頬板が掴む面
# 片側すきま。FDM は外寸が大きめ・内寸が小さめに出るので 0.3 では嵌らない
# 恐れがある。0.4 にすると寸法誤差 ±0.2 を吸収できる。
# クランプは摩擦締結なので、締めれば頬板が 0.4 mm たわんでタブに密着する
# (必要な力は約 91 N。予圧 875 N に対して 10% 程度)。
TAB_FIT = 0.4                 # 片側すきま
# ユーザーが Pad_A2_CheekBlock の押し出しを 34.6 -> 40 にしたのを採用。
#   押し出し量 = 2 * CHEEK_XO = 2 * (TAB_W/2 + TAB_FIT + CHEEK_T)
#   = 2 * (12 + 0.3 + 7.7) = 40。頬板は 5 -> 7.7 mm 厚になる。
CHEEK_T = 7.7                 # 頬板厚
CHEEK_XI = TAB_W / 2.0 + TAB_FIT       # 頬板内面 X
CHEEK_XO = CHEEK_XI + CHEEK_T          # 頬板外面 X
TAB_END_R = TAB_W / 2.0

# --- CAM_MOUNT : 背面プレート -----------------------------------------
PLATE_T = 6.0                 # 板厚 (Y -3..+3)
PLATE_HW = 67.0               # 半幅 -> 全幅 134

# --- D455 -------------------------------------------------------------
CAM_W, CAM_H, CAM_D = 124.0, 29.0, 26.0
# CAM_Y0 (カメラ背面 = プレート前面) は DERIVED で PLATE_Y1 として計算する
M4_PITCH = 95.0
CAM_MASS = 0.116              # kg

# --- CAM_MOUNT : 上端リブ / シェルフ ----------------------------------
RIB_H = 7.0
# ユーザーが 03_CAM_MOUNT で 8 -> 17 に深くしたのを採用。
# 前後曲げの I_zz が 3126 -> 13779 mm4 (4.4倍) になる。追加 10.7 g。
RIB_DEPTH = 17.0
SHELF_T = 6.0
SHELF_DEPTH = 14.0
SHELF_MID_HW = TAB_W / 2.0
SHELF_OUT_X0 = 22.0           # USB-C (|X|~46.5) と M2 ねじ (37/56) を避ける
SHELF_OUT_X1 = 33.0


# =====================================================================
# DERIVED  — FASTENERS から逆算する寸法。直接書き換えないこと
# =====================================================================
def _f(k, a):
    return FASTENERS[k][a]


# バカ穴径
CLEAR_D_M3 = _f('base', 'clear')
PIV_D = _f('pivot', 'clear')
ARC_W = _f('clamp', 'clear')
CLEAR_D_M4 = _f('cam', 'clear')

_wc = _f('clamp', 'washer_od') / 2.0        # クランプ側ワッシャ半径
_wp = _f('pivot', 'washer_od') / 2.0        # 回転軸側ワッシャ半径

# ★ ベース板はタワーの footprint に「揃える」。はみ出させない
BASE_HW = TOWER_W / 2.0
BASE_HD = TOWER_D / 2.0

# ★ 回転軸 Y。ここがピッチ範囲を直接決める:
#     PIV_Y + ARC_R*sin(SPAN) + クランプ座金R + SEAT_MARGIN <= BASE_HD
#   1.5 が ±13deg を保てる上限。大きくするとピッチが減り、小さくすると増える。
PIV_Y = PIV_Y_WANT
# プレート (= カメラ背面) の Y 位置は PIV_Y と TAB_T から逆算する。
# タブの裏面はプレートの裏面と面一 (印刷でベッドに接する面) でなければならない。
PLATE_Y0 = PIV_Y - TAB_T / 2.0          # プレート裏面 = タブ裏面 = ベッド面
PLATE_Y1 = PLATE_Y0 + PLATE_T           # プレート前面 = カメラ背面
PLATE_YM = (PLATE_Y0 + PLATE_Y1) / 2.0  # プレート厚の中心 (対称パッドの基準)

# 円弧半径: 回転軸ボルトとクランプボルトのワッシャが当たらない距離が下限
ARC_R_MIN = _wp + _wc + FASTENER_CLEAR
ARC_R = max(ARC_R_WANT, ARC_R_MIN)

# 振り角: クランプ穴の Y 振れ (ARC_R*sin) + ワッシャ + 余白 がベース奥行に収まる範囲まで落とす
_span_room = BASE_HD - PIV_Y - _wc - SEAT_MARGIN
ARC_SPAN = math.floor(min(
    ARC_SPAN_WANT,
    math.degrees(math.asin(max(0.0, min(1.0, _span_room / ARC_R))))))
ARC_SPAN_OK = ARC_SPAN >= ARC_SPAN_MIN

_sin = math.sin(math.radians(ARC_SPAN))
_cos = math.cos(math.radians(ARC_SPAN))
_dY = ARC_R * _sin                          # クランプ穴の Y 振れ幅

# 回転軸 Z: タブ下端の角がベース板上面に当たらない最小高さを逆算。
# タブ下端の角は回転軸から見て半径 _rc の位置にあり、±SPAN 回すと
# 最大 _rc まで真下に来る。
_rc = math.hypot(TAB_T / 2.0, TAB_END_R)    # タブ断面の対角半径
PIV_Z = BASE_Z1 + BASE_CLEAR + _rc

# 頬板の Y。座面の要求を満たす最小値は下の 2 つ。
CHEEK_Y1_MIN = max(PIV_Y + _dY + _wc, PIV_Y + _wp) + SEAT_MARGIN
CHEEK_Y0_MAX = min(PIV_Y - _dY - _wc, PIV_Y - _wp) - SEAT_MARGIN
# ★ ただし最小値ぴったりにする理由は無いので、タワーの footprint いっぱいまで
#   広げて剛性を稼ぐ。ここを footprint より大きくすると横にはみ出すので、
#   BASE_HD でクランプするのが正解 (はみ出し事故はこれで防ぐ)。
CHEEK_Y1 = BASE_HD
CHEEK_Y0 = -BASE_HD
CHEEK_Z1 = PIV_Z + ARC_R + _wc + SEAT_MARGIN
CLAMP_Z = PIV_Z + ARC_R

# タワー取付穴の X: 頬板外面からワッシャ + 工具ぶん逃がした最小位置
_wb = _f('base', 'washer_od') / 2.0
_tool_b = max(_f('base', 'tool_d') / 2.0, _wb)
FIX_X = CHEEK_XO + _tool_b + SEAT_MARGIN
FIX_Y = BASE_HD - _wb - SEAT_MARGIN
# 成立条件: ワッシャがベース縁からはみ出さない / インサートの縁あき 2 mm 以上
FIX_X_OK = (FIX_X + _wb + SEAT_MARGIN <= BASE_HW
            and FIX_X + INSERT_D / 2.0 + 2.0 <= TOWER_W / 2.0)
FIX_Y_OK = (FIX_Y + _wb + SEAT_MARGIN <= BASE_HD
            and FIX_Y + INSERT_D / 2.0 + 2.0 <= TOWER_D / 2.0)
# 分割版 (タワーとヨークを M3 x4 で締結する構成) が成立するか。
# TAB_W を広げると頬板が太り、座金が頬板とベース縁の間に入らなくなる。
# 成立しないときは取付穴そのものを作らない = 一体版 (04) 専用の構成になる。
FIX_FITS = FIX_X_OK and FIX_Y_OK
SPLIT_TAB_W_MAX = 2.0 * (BASE_HW - 2.0 * (_wb + SEAT_MARGIN) - TAB_FIT - CHEEK_T)
CHEEK_FIT_OK = (CHEEK_Y1 <= BASE_HD and CHEEK_Y0 >= -BASE_HD
                and CHEEK_Y1 >= CHEEK_Y1_MIN - 1e-9
                and CHEEK_Y0 <= CHEEK_Y0_MAX + 1e-9)

# カメラ底面 Z: 回転時に CAM_MOUNT 後下角が頬板上端に当たらない高さを逆算
_u = abs(PLATE_Y0 - PIV_Y)    # = TAB_T/2。回転時に一番下がる角の水平距離
CAM_Z0 = PIV_Z + math.ceil(
    (CHEEK_Z1 + SWING_CLEAR - PIV_Z + _u * _sin) / _cos)
CAM_Y0 = PLATE_Y1             # カメラ背面 = プレート前面
M4_Z = CAM_Z0 + CAM_H / 2.0   # 背面 M4 の高さ = 光軸高さ
PLATE_Z0 = CAM_Z0
SHELF_Z0 = CAM_Z0 - SHELF_T
RIB_Z0 = CAM_Z0 + CAM_H + 1.0
PLATE_Z1 = RIB_Z0 + RIB_H

# 予圧 F = T / (0.2 d)
PRELOAD = {k: _f(k, 'torque') / (0.2 * _f(k, 'nom_d') / 1000.0) for k in FASTENERS}

# --- 表示色 -----------------------------------------------------------
COL_TOWER = (0.55, 0.55, 0.58)
COL_ADJ = (0.95, 0.55, 0.10)
COL_CAM = (0.20, 0.55, 0.90)
COL_REF = (0.20, 0.80, 0.35)
COL_BOLT = (0.85, 0.15, 0.15)
COL_TOOL = (0.95, 0.85, 0.20)


# =====================================================================
# helpers
# =====================================================================

def v(x, y):
    return App.Vector(x, y, 0)


def add_closed_loop(sk, geoms):
    first = len(sk.Geometry)
    for g, _s, _e in geoms:
        sk.addGeometry(g, False)
    n = len(geoms)
    for i in range(n):
        sk.addConstraint(Sketcher.Constraint(
            'Coincident', first + i, 2, first + (i + 1) % n, 1))
    return first


def arc(cx, cy, r, a1_deg, a2_deg):
    c = Part.Circle(App.Vector(cx, cy, 0), App.Vector(0, 0, 1), r)
    a = Part.ArcOfCircle(c, math.radians(a1_deg), math.radians(a2_deg))
    s = (cx + r * math.cos(math.radians(a1_deg)), cy + r * math.sin(math.radians(a1_deg)))
    e = (cx + r * math.cos(math.radians(a2_deg)), cy + r * math.sin(math.radians(a2_deg)))
    return (a, s, e)


def line(p1, p2):
    return (Part.LineSegment(v(*p1), v(*p2)), p1, p2)


def rect(x0, y0, x1, y1):
    return [line((x0, y0), (x1, y0)), line((x1, y0), (x1, y1)),
            line((x1, y1), (x0, y1)), line((x0, y1), (x0, y0))]


def origin_plane(body, tag):
    for f in body.Origin.OriginFeatures:
        if f.Role == tag:
            return f
    raise RuntimeError("origin plane not found: " + tag)


def new_sketch(doc, body, name, plane_role, offset=None):
    """XY_Plane: offset = グローバル Z / XZ_Plane: グローバル Y = -offset
       YZ_Plane: グローバル X = +offset"""
    sk = doc.addObject('Sketcher::SketchObject', name)
    body.addObject(sk)
    sk.AttachmentSupport = [(origin_plane(body, plane_role), '')]
    sk.MapMode = 'FlatFace'
    if offset:
        sk.AttachmentOffset = App.Placement(App.Vector(0, 0, offset),
                                            App.Rotation(0, 0, 0, 1))
    return sk


def pad(doc, body, name, sk, length, midplane=False, reversed_=False):
    p = doc.addObject('PartDesign::Pad', name)
    body.addObject(p)
    p.Profile = sk
    p.Length = length
    p.Midplane = midplane
    p.Reversed = reversed_
    doc.recompute()
    return p


def pocket(doc, body, name, sk, length=None, through=False, midplane=False):
    p = doc.addObject('PartDesign::Pocket', name)
    body.addObject(p)
    p.Profile = sk
    if through:
        p.Type = 1
    else:
        p.Type = 0
        p.Length = length
    p.Midplane = midplane
    doc.recompute()
    return p


def fully_constrain(sk):
    """水平/垂直 → 半径・中心座標 → 端点座標 の順に「原点からの寸法拘束」を
    貪欲に足して完全拘束にする。冗長・矛盾になったものは即座に取り消す。
    生成直後の座標をそのまま拘束値にするので形は一切動かない。"""
    def state():
        sk.solve()
        return sk.DoF, len(sk.RedundantConstraints), len(sk.ConflictingConstraints)

    def try_add(c):
        dof0 = state()[0]
        if dof0 == 0:
            return False
        try:
            n = sk.addConstraint(c)
        except Exception:
            return False
        dof1, red, con = state()
        if dof1 >= dof0 or red or con:
            sk.delConstraint(n)
            sk.solve()
            return False
        return True

    def fix_x(gi, pos, x):
        if abs(x) < 1e-7:
            return try_add(Sketcher.Constraint('PointOnObject', gi, pos, -2))
        return try_add(Sketcher.Constraint('DistanceX', gi, pos, x))

    def fix_y(gi, pos, y):
        if abs(y) < 1e-7:
            return try_add(Sketcher.Constraint('PointOnObject', gi, pos, -1))
        return try_add(Sketcher.Constraint('DistanceY', gi, pos, y))

    geo = sk.Geometry
    for i, g in enumerate(geo):
        if g.TypeId == 'Part::GeomLineSegment':
            dx = abs(g.EndPoint.x - g.StartPoint.x)
            dy = abs(g.EndPoint.y - g.StartPoint.y)
            if dy < 1e-7 < dx:
                try_add(Sketcher.Constraint('Horizontal', i))
            elif dx < 1e-7 < dy:
                try_add(Sketcher.Constraint('Vertical', i))
    for i, g in enumerate(geo):
        if g.TypeId in ('Part::GeomCircle', 'Part::GeomArcOfCircle'):
            try_add(Sketcher.Constraint('Radius', i, g.Radius))
            fix_x(i, 3, g.Center.x)
            fix_y(i, 3, g.Center.y)
    for i, g in enumerate(geo):
        if g.TypeId not in ('Part::GeomLineSegment', 'Part::GeomArcOfCircle'):
            continue
        for pos, p in ((1, g.StartPoint), (2, g.EndPoint)):
            fix_x(i, pos, p.x)
            fix_y(i, pos, p.y)
    return state()


def set_color(obj, rgb, transparency=0):
    if not HAS_GUI:
        return
    try:
        obj.ViewObject.ShapeColor = rgb
        obj.ViewObject.Transparency = transparency
    except Exception:
        pass


# ---------------------------------------------------------------------
# 締結部品の実形状
# ---------------------------------------------------------------------

def hexprism(af, height, base, direction):
    """二面幅 af の六角柱。ナット用。"""
    r = af / math.sqrt(3.0)            # 対角半径
    d = App.Vector(*direction).normalize()
    pts = []
    for i in range(6):
        a = math.radians(60 * i)
        pts.append(App.Vector(r * math.cos(a), r * math.sin(a), 0))
    pts.append(pts[0])
    wire = Part.makePolygon(pts)
    face = Part.Face(wire)
    prism = face.extrude(App.Vector(0, 0, height))
    # +Z から d へ回す
    rot = App.Rotation(App.Vector(0, 0, 1), d)
    prism.Placement = App.Placement(App.Vector(*base), rot)
    return prism


def fastener_shape(key, seat_pt, direction, grip, nut=True, tool=False):
    """seat_pt: ボルト頭側の座面(部品の面)の点。direction: ねじが部品を貫く向き。
    grip: 締結される厚み。戻り値は (締結部品ソリッド, 工具空間ソリッド or None)"""
    s = FASTENERS[key]
    d = App.Vector(*direction).normalize()
    p0 = App.Vector(*seat_pt)
    parts = []
    wt, hh = s['washer_t'], s['head_h']
    # 軸: ワッシャ厚 + 掴み厚 (+ ナット止めならワッシャ + ナット + 余り 2)
    shank_len = wt + grip + ((wt + s['nut_h'] + 2.0) if (nut and s['nut_af'] > 0) else 0.0)
    parts.append(Part.makeCylinder(s['nom_d'] / 2.0, shank_len, p0 - d * wt, d))
    # 頭側ワッシャ + 頭
    parts.append(Part.makeCylinder(s['washer_od'] / 2.0, wt, p0 - d * wt, d))
    parts.append(Part.makeCylinder(s['head_d'] / 2.0, hh, p0 - d * (wt + hh), d))
    tool_solid = None
    if s['tool_d'] > 0:
        tool_solid = Part.makeCylinder(s['tool_d'] / 2.0, hh + 12.0,
                                       p0 - d * (wt + hh + 12.0), d)
    if nut and s['nut_af'] > 0:
        e = p0 + d * grip
        parts.append(Part.makeCylinder(s['washer_od'] / 2.0, wt, e, d))
        parts.append(hexprism(s['nut_af'], s['nut_h'], e + d * wt, d))
        t2 = Part.makeCylinder(s['tool_d'] / 2.0, s['nut_h'] + 12.0, e + d * wt, d)
        tool_solid = t2 if tool_solid is None else tool_solid.fuse(t2)
    sol = parts[0]
    for q in parts[1:]:
        sol = sol.fuse(q)
    return sol.removeSplitter(), (tool_solid if tool else None)


def seat_rim(key, seat_pt, direction, into=0.05, band=1.0, t=0.4):
    """ワッシャ外周 1 mm 幅のリングを母材側に 0.05 mm 沈めた薄板。
    これが母材から食み出していないか (cut の体積が 0 か) で座面を検査する。"""
    s = FASTENERS[key]
    d = App.Vector(*direction).normalize()
    p0 = App.Vector(*seat_pt) + d * into
    ro = s['washer_od'] / 2.0
    outer = Part.makeCylinder(ro, t, p0, d)
    inner = Part.makeCylinder(max(ro - band, 0.1), t, p0, d)
    return outer.cut(inner)


# =====================================================================
# ドキュメント内部名は開き直すと変わる (Unnamed -> タワー) ので、
# まず内部名で探し、無ければファイル名で引き当てる。
doc = App.listDocuments().get(DOC_NAME)
if doc is None:
    import os as _os
    _p = _os.path.join(_os.path.dirname(__file__), 'タワー.FCStd')
    for _d in App.listDocuments().values():
        if _d.FileName and _os.path.normcase(_d.FileName) == _os.path.normcase(_p):
            doc = _d
            break
    if doc is None:
        doc = App.openDocument(_p)
print('master doc:', doc.Name, '|', doc.Label)

# タワー本体は名前が 'Body' でないこともある (部品ファイルからコピーし直した場合)。
# ADJUSTER / CAM_MOUNT 以外の PartDesign::Body を拾う。
tower = doc.getObject('Body')
if tower is None:
    cands = [o for o in doc.Objects
             if o.TypeId == 'PartDesign::Body' and o.Name not in ('ADJUSTER', 'CAM_MOUNT')]
    if not cands:
        raise RuntimeError('タワー本体の Body が見つからない')
    tower = cands[0]
print('tower body:', tower.Name, '|', tower.Label, '| BB:', tower.Shape.BoundBox)

# ---------------------------------------------------------------------
# 0) 生成物だけ作り直す (ユーザーが描いた Sketch/Pad/Pocket/Pocket001 は触らない)
# ---------------------------------------------------------------------
for bname in ('ADJUSTER', 'CAM_MOUNT'):
    b = doc.getObject(bname)
    if b is not None:
        for child in list(b.Group):
            try:
                doc.removeObject(child.Name)
            except Exception:
                pass
        try:
            doc.removeObject(b.Origin.Name)
        except Exception:
            pass
        doc.removeObject(bname)
for o in list(doc.Objects):
    if o.Name.startswith('REF_') or o.Name == 'D455_REF':
        doc.removeObject(o.Name)
# タワーのインサート穴もパラメータ追従させるため毎回作り直す
for n in ('Pocket_TowerInserts', 'Sketch_TowerInserts'):
    if doc.getObject(n) is not None:
        doc.removeObject(n)
doc.recompute()


# =====================================================================
# 1) タワー上面に M3 熱圧入インサート用の下穴
# =====================================================================
if FIX_FITS:
    sk = new_sketch(doc, tower, 'Sketch_TowerInserts', 'XY_Plane', offset=TOWER_TOP_Z)
    for sx in (-1, 1):
        for sy in (-1, 1):
            sk.addGeometry(Part.Circle(v(sx * FIX_X, sy * FIX_Y),
                                       App.Vector(0, 0, 1), INSERT_D / 2.0), False)
    pocket(doc, tower, 'Pocket_TowerInserts', sk, length=INSERT_DEPTH)
else:
    print('*** 分割版の M3 取付穴は成立しないので作らない (一体版 04 専用の構成) ***')
    print('    分割版も残したいなら TAB_W <= %.1f にすること (現在 %.1f)'
          % (SPLIT_TAB_W_MAX, TAB_W))
    # ★ 最終フィーチャを消すと Body.Tip が None になり、以後 Shape が invalid になる。
    #   残っている最後の PartDesign フィーチャに付け直す。
    feats = [o for o in tower.Group if o.TypeId.startswith('PartDesign::')]
    if feats and tower.Tip is None:
        tower.Tip = feats[-1]
        doc.recompute()
        print('    Body.Tip を %s に付け直した' % tower.Tip.Name)


# =====================================================================
# 2) ADJUSTER  ピッチ角調整ヨーク
# =====================================================================
adj = doc.addObject('PartDesign::Body', 'ADJUSTER')
adj.Label = 'ADJUSTER_ピッチ調整'

sk = new_sketch(doc, adj, 'Sk_A1_Base', 'XY_Plane', offset=BASE_Z0)
add_closed_loop(sk, rect(-BASE_HW, -BASE_HD, BASE_HW, BASE_HD))
pad(doc, adj, 'Pad_A1_Base', sk, BASE_T)

sk = new_sketch(doc, adj, 'Sk_A2_CheekProfile', 'YZ_Plane')
add_closed_loop(sk, rect(CHEEK_Y0, BASE_Z1, CHEEK_Y1, CHEEK_Z1))
pad(doc, adj, 'Pad_A2_CheekBlock', sk, 2.0 * CHEEK_XO, midplane=True)

sk = new_sketch(doc, adj, 'Sk_A3_Gap', 'XY_Plane', offset=CHEEK_Z1)
add_closed_loop(sk, rect(-CHEEK_XI, CHEEK_Y0 - 2, CHEEK_XI, CHEEK_Y1 + 2))
pocket(doc, adj, 'Pocket_A3_Gap', sk, length=CHEEK_Z1 - BASE_Z1)

if FIX_FITS:
    sk = new_sketch(doc, adj, 'Sk_A4_FixHoles', 'XY_Plane', offset=BASE_Z1)
    for sx in (-1, 1):
        for sy in (-1, 1):
            sk.addGeometry(Part.Circle(v(sx * FIX_X, sy * FIX_Y),
                                       App.Vector(0, 0, 1), CLEAR_D_M3 / 2.0), False)
    pocket(doc, adj, 'Pocket_A4_FixHoles', sk, length=BASE_T)

sk = new_sketch(doc, adj, 'Sk_A5_PivotArc', 'YZ_Plane')
sk.addGeometry(Part.Circle(v(PIV_Y, PIV_Z), App.Vector(0, 0, 1), PIV_D / 2.0), False)
ri, ro = ARC_R - ARC_W / 2.0, ARC_R + ARC_W / 2.0
p1, p2 = 90.0 - ARC_SPAN, 90.0 + ARC_SPAN
c1 = (PIV_Y + ARC_R * math.cos(math.radians(p1)), PIV_Z + ARC_R * math.sin(math.radians(p1)))
c2 = (PIV_Y + ARC_R * math.cos(math.radians(p2)), PIV_Z + ARC_R * math.sin(math.radians(p2)))
i_out = sk.addGeometry(arc(PIV_Y, PIV_Z, ro, p1, p2)[0], False)
i_in = sk.addGeometry(arc(PIV_Y, PIV_Z, ri, p1, p2)[0], False)
i_c1 = sk.addGeometry(arc(c1[0], c1[1], ARC_W / 2.0, p1 + 180, p1 + 360)[0], False)
i_c2 = sk.addGeometry(arc(c2[0], c2[1], ARC_W / 2.0, p2, p2 + 180)[0], False)
for a_, pa, b_, pb in ((i_c1, 2, i_out, 1), (i_out, 2, i_c2, 1),
                       (i_c2, 2, i_in, 2), (i_in, 1, i_c1, 1)):
    sk.addConstraint(Sketcher.Constraint('Coincident', a_, pa, b_, pb))
pocket(doc, adj, 'Pocket_A5_PivotArc', sk, through=True, midplane=True)

set_color(adj, COL_ADJ)


# =====================================================================
# 3) CAM_MOUNT  D455 固定治具
# =====================================================================
cam = doc.addObject('PartDesign::Body', 'CAM_MOUNT')
cam.Label = 'CAM_MOUNT_D455'

tw = TAB_W / 2.0
aX, bX = SHELF_OUT_X0, SHELF_OUT_X1

sk = new_sketch(doc, cam, 'Sk_C1_Plate', 'XZ_Plane', offset=-PLATE_YM)
add_closed_loop(sk, [
    line((-PLATE_HW, PLATE_Z1), (-PLATE_HW, PLATE_Z0)),
    line((-PLATE_HW, PLATE_Z0), (-bX, PLATE_Z0)),
    line((-bX, PLATE_Z0), (-bX, SHELF_Z0)),
    line((-bX, SHELF_Z0), (-aX, SHELF_Z0)),
    line((-aX, SHELF_Z0), (-aX, PLATE_Z0)),
    line((-aX, PLATE_Z0), (-tw, PLATE_Z0)),
    line((-tw, PLATE_Z0), (-tw, PIV_Z)),
    arc(0.0, PIV_Z, TAB_END_R, 180, 360),
    line((tw, PIV_Z), (tw, PLATE_Z0)),
    line((tw, PLATE_Z0), (aX, PLATE_Z0)),
    line((aX, PLATE_Z0), (aX, SHELF_Z0)),
    line((aX, SHELF_Z0), (bX, SHELF_Z0)),
    line((bX, SHELF_Z0), (bX, PLATE_Z0)),
    line((bX, PLATE_Z0), (PLATE_HW, PLATE_Z0)),
    line((PLATE_HW, PLATE_Z0), (PLATE_HW, PLATE_Z1)),
    line((PLATE_HW, PLATE_Z1), (-PLATE_HW, PLATE_Z1)),
])
pad(doc, cam, 'Pad_C1_Plate', sk, PLATE_T, midplane=True)

sk = new_sketch(doc, cam, 'Sk_C2_TabBoss', 'XZ_Plane', offset=-PIV_Y)
add_closed_loop(sk, [
    line((-tw, PLATE_Z0), (-tw, PIV_Z)),
    arc(0.0, PIV_Z, TAB_END_R, 180, 360),
    line((tw, PIV_Z), (tw, PLATE_Z0)),
    line((tw, PLATE_Z0), (-tw, PLATE_Z0)),
])
pad(doc, cam, 'Pad_C2_TabBoss', sk, TAB_T, midplane=True)

sk = new_sketch(doc, cam, 'Sk_C3_Shelf', 'XY_Plane', offset=SHELF_Z0)
y0 = PLATE_Y1                 # プレート前面から前へ出す
for x0, x1 in ((-SHELF_OUT_X1, -SHELF_OUT_X0),
               (-SHELF_MID_HW, SHELF_MID_HW),
               (SHELF_OUT_X0, SHELF_OUT_X1)):
    add_closed_loop(sk, rect(x0, y0, x1, y0 + SHELF_DEPTH))
pad(doc, cam, 'Pad_C3_Shelf', sk, SHELF_T)

sk = new_sketch(doc, cam, 'Sk_C4_TopRib', 'XY_Plane', offset=RIB_Z0)
add_closed_loop(sk, rect(-PLATE_HW, y0, PLATE_HW, y0 + RIB_DEPTH))
pad(doc, cam, 'Pad_C4_TopRib', sk, RIB_H)

sk = new_sketch(doc, cam, 'Sk_C5_CamHoles', 'XZ_Plane', offset=-PLATE_YM)
for sx in (-1, 1):
    sk.addGeometry(Part.Circle(v(sx * M4_PITCH / 2.0, M4_Z),
                               App.Vector(0, 0, 1), CLEAR_D_M4 / 2.0), False)
pocket(doc, cam, 'Pocket_C5_CamHoles', sk, through=True, midplane=True)

sk = new_sketch(doc, cam, 'Sk_C6_JointHoles', 'YZ_Plane')
sk.addGeometry(Part.Circle(v(PIV_Y, PIV_Z), App.Vector(0, 0, 1), PIV_D / 2.0), False)
sk.addGeometry(Part.Circle(v(PIV_Y, CLAMP_Z), App.Vector(0, 0, 1), PIV_D / 2.0), False)
pocket(doc, cam, 'Pocket_C6_JointHoles', sk, through=True, midplane=True)

set_color(cam, COL_CAM)


# =====================================================================
# 4) 参照物 (印刷対象外): D455 外形 と 締結部品一式
# =====================================================================
ref = doc.addObject('Part::Box', 'D455_REF')
ref.Label = 'D455_参照外形_印刷対象外'
ref.Length, ref.Width, ref.Height = CAM_W, CAM_D, CAM_H
ref.Placement = App.Placement(App.Vector(-CAM_W / 2.0, CAM_Y0, CAM_Z0), App.Rotation())
set_color(ref, COL_REF, 70)

# 締結部品の定義: key, 座面点, 貫通方向, 掴み厚, ナット有無
FASTENER_SITES = [
    ('pivot', 'REF_BoltPivot', '回転軸',
     (-CHEEK_XO, PIV_Y, PIV_Z), (1, 0, 0), 2 * CHEEK_XO, True),
    ('clamp', 'REF_BoltClamp', 'クランプ',
     (-CHEEK_XO, PIV_Y, CLAMP_Z), (1, 0, 0), 2 * CHEEK_XO, True),
    ('cam', 'REF_BoltCamL', 'カメラ左',
     (-M4_PITCH / 2.0, PLATE_Y0, M4_Z), (0, 1, 0), PLATE_T + ENGAGE['cam'], False),
    ('cam', 'REF_BoltCamR', 'カメラ右',
     (M4_PITCH / 2.0, PLATE_Y0, M4_Z), (0, 1, 0), PLATE_T + ENGAGE['cam'], False),
]
# 分割版が成立しないときはタワー固定ボルトそのものが存在しない
if FIX_FITS:
    for sx in (-1, 1):
        for sy in (-1, 1):
            FASTENER_SITES.append(
                ('base', 'REF_BoltBase%s%s' % ('L' if sx < 0 else 'R', 'B' if sy < 0 else 'F'),
                 'タワー固定', (sx * FIX_X, sy * FIX_Y, BASE_Z1), (0, 0, -1),
                 BASE_T + ENGAGE['base'], False))

fast_objs = {}
for key, name, jp, pt, d, grip, nut in FASTENER_SITES:
    sol, _ = fastener_shape(key, pt, d, grip, nut=nut)
    o = doc.addObject('Part::Feature', name)
    o.Label = 'REF_%s_%s_印刷対象外' % (jp, FASTENERS[key]['label'])
    o.Shape = sol
    set_color(o, COL_BOLT, 20)
    fast_objs[name] = (key, pt, d, grip, nut, o)

set_color(tower, COL_TOWER)
doc.recompute()


# =====================================================================
# 4.5) 生成したスケッチを完全拘束にする
# =====================================================================
print('--- constraining sketches ---')
for b in (tower, adj, cam):
    for o in b.Group:
        if o.TypeId != 'Sketcher::SketchObject':
            continue
        if o.FullyConstrained:
            print('  %-22s already fully constrained' % o.Name)
            continue
        dof, red, con = fully_constrain(o)
        print('  %-22s DoF=%d red=%d con=%d constraints=%d -> %s'
              % (o.Name, dof, red, con, o.ConstraintCount,
                 'OK' if (dof == 0 and not red and not con) else 'NOT FULLY CONSTRAINED'))
doc.recompute()


# =====================================================================
# 5) 検証
# =====================================================================
NG = []


def check(cond, msg):
    print('  [%s] %s' % ('OK' if cond else 'NG', msg))
    if not cond:
        NG.append(msg)


print('--- derived dimensions ---')
print('  BASE       %.1f (X) x %.1f (Y) x %.1f  Z %.1f..%.1f   (タワーは %.0f x %.0f)'
      % (2 * BASE_HW, 2 * BASE_HD, BASE_T, BASE_Z0, BASE_Z1, TOWER_W, TOWER_D))
print('  CHEEK      X %.2f..%.2f  Y %.2f..%.2f  Z %.1f..%.1f'
      % (CHEEK_XI, CHEEK_XO, CHEEK_Y0, CHEEK_Y1, BASE_Z1, CHEEK_Z1))
print('  FIX        X %.2f  Y %.2f  (タワー縁あき X %.2f / Y %.2f)'
      % (FIX_X, FIX_Y, TOWER_W / 2.0 - FIX_X - INSERT_D / 2.0,
         TOWER_D / 2.0 - FIX_Y - INSERT_D / 2.0))
print('  CAM_Z0     %.1f   光軸 Z %.1f   PLATE Z %.1f..%.1f'
      % (CAM_Z0, M4_Z, PLATE_Z0, PLATE_Z1))
print('  ピッチ     +/- %.0f deg (円弧長穴の端がストッパ)' % ARC_SPAN)

print('--- shapes ---')
for o in (tower, adj, cam):
    s = o.Shape
    print('  %-10s solids=%d vol=%9.1f mm3 mass(PETG)=%5.1f g'
          % (o.Name, len(s.Solids), s.Volume, s.Volume * 1.27e-3))
    check(len(s.Solids) == 1, '%s が単一ソリッド' % o.Name)
check(not [o.Name for o in doc.Objects
           if getattr(o, 'State', None) and 'Invalid' in o.State], 'Invalid フィーチャ無し')
if FIX_FITS:
    check(FIX_X_OK, 'タワー取付穴の X 位置が成立 (頬板とベース縁の両方からワッシャが逃げる)')
    check(FIX_Y_OK, 'タワー取付穴の Y 位置が成立')
else:
    print('  [--] 分割版は成立しない (TAB_W %.1f > 上限 %.1f)。一体版 04 のみ有効'
          % (TAB_W, SPLIT_TAB_W_MAX))
check(CHEEK_FIT_OK,
      '頬板 Y %.2f..%.2f が footprint ±%.1f に収まり、座面の要求 (%.2f..%.2f) も満たす'
      % (CHEEK_Y0, CHEEK_Y1, BASE_HD, CHEEK_Y0_MAX, CHEEK_Y1_MIN))
# ★ タワーより下側の部品が footprint から横にはみ出していないか
_ab = adj.Shape.BoundBox
_ovr = max(_ab.XMax - TOWER_W / 2.0, -TOWER_W / 2.0 - _ab.XMin,
           _ab.YMax - TOWER_D / 2.0, -TOWER_D / 2.0 - _ab.YMin)
check(_ovr <= 1e-6, 'ADJUSTER がタワー footprint からはみ出さない (最大 %+.2f mm)' % _ovr)

_total_h = max(cam.Shape.BoundBox.ZMax, adj.Shape.BoundBox.ZMax, tower.Shape.BoundBox.ZMax)
check(_total_h <= MAX_TOTAL_H,
      '全体高さ %.1f mm <= %.0f mm (タワー底面基準)' % (_total_h, MAX_TOTAL_H))
check(abs(BASE_HW * 2 - TOWER_W) < 1e-6 and abs(BASE_HD * 2 - TOWER_D) < 1e-6,
      'ADJUSTER ベースがタワー footprint と一致 (%.1f x %.1f)' % (BASE_HW * 2, BASE_HD * 2))

print('--- bolt axis clearance (0 = 貫通OK) ---')
for nm, z in (('PIVOT', PIV_Z), ('CLAMP', CLAMP_Z)):
    c = Part.makeCylinder(FASTENERS['pivot']['nom_d'] / 2.0, 80,
                          App.Vector(-40, PIV_Y, z), App.Vector(1, 0, 0))
    va, vc = c.common(adj.Shape).Volume, c.common(cam.Shape).Volume
    print('  %-6s along X: ADJUSTER=%6.2f  CAM_MOUNT=%6.2f' % (nm, va, vc))
    check(va < 1e-6 and vc < 1e-6, '%s ボルト軸が両部品を貫通' % nm)
for sx in (-1, 1):
    c = Part.makeCylinder(FASTENERS['cam']['nom_d'] / 2.0, 60,
                          App.Vector(sx * M4_PITCH / 2.0, -30, M4_Z), App.Vector(0, 1, 0))
    check(c.common(cam.Shape).Volume < 1e-6, 'カメラ M4 (X=%+.1f) が貫通' % (sx * M4_PITCH / 2))

print('--- washer seat / fastener interference over pitch range ---')
# 座面判定は「長穴や穴をまたぐ分」を食み出しに数えないよう、
# 穴を開ける前の素材ブロック (頬板・ベース板・背面プレート) を基準にする。
SEAT_REF = {
    'cheekL': Part.makeBox(CHEEK_T, CHEEK_Y1 - CHEEK_Y0, CHEEK_Z1 - BASE_Z1,
                           App.Vector(-CHEEK_XO, CHEEK_Y0, BASE_Z1)),
    'cheekR': Part.makeBox(CHEEK_T, CHEEK_Y1 - CHEEK_Y0, CHEEK_Z1 - BASE_Z1,
                           App.Vector(CHEEK_XI, CHEEK_Y0, BASE_Z1)),
    'base':   Part.makeBox(2 * BASE_HW, 2 * BASE_HD, BASE_T,
                           App.Vector(-BASE_HW, -BASE_HD, BASE_Z0)),
    'plate':  Part.makeBox(2 * PLATE_HW, PLATE_T, PLATE_Z1 - PLATE_Z0,
                           App.Vector(-PLATE_HW, PLATE_Y0, PLATE_Z0)),
}
PIVV = App.Vector(0, PIV_Y, PIV_Z)
angles = [-ARC_SPAN, -ARC_SPAN / 2, 0, ARC_SPAN / 2, ARC_SPAN]
worst_seat, worst_hit = 0.0, 0.0
for deg in angles:
    pl = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), deg), PIVV)
    cam_s = cam.Shape.copy(); cam_s.transformShape(pl.Matrix)
    ref_s = ref.Shape.copy(); ref_s.transformShape(pl.Matrix)
    seat_d = worst_seat
    hit_d = worst_hit
    worst_hit = max(worst_hit, adj.Shape.common(cam_s).Volume,
                    adj.Shape.common(ref_s).Volume)
    # クランプ穴の位置。X 軸まわり +deg の回転は Y' = Y cos - Z sin なので符号は負
    ang = math.radians(deg)
    cy = PIV_Y - ARC_R * math.sin(ang)
    cz = PIV_Z + ARC_R * math.cos(ang)
    for key, pt, into_dir, tgt in (
            ('pivot', (-CHEEK_XO, PIV_Y, PIV_Z), (1, 0, 0), 'cheekL'),
            ('pivot', (CHEEK_XO, PIV_Y, PIV_Z), (-1, 0, 0), 'cheekR'),
            ('clamp', (-CHEEK_XO, cy, cz), (1, 0, 0), 'cheekL'),
            ('clamp', (CHEEK_XO, cy, cz), (-1, 0, 0), 'cheekR')):
        rim = seat_rim(key, pt, into_dir)
        worst_seat = max(worst_seat, rim.cut(SEAT_REF[tgt]).Volume)
    # 頭 / ナット / 工具の空間が、回る部品と当たらないか
    for key, pt, d in (('pivot', (-CHEEK_XO, PIV_Y, PIV_Z), (1, 0, 0)),
                       ('clamp', (-CHEEK_XO, cy, cz), (1, 0, 0))):
        sol, tool = fastener_shape(key, pt, d, 2 * CHEEK_XO, nut=True, tool=True)
        env = sol.fuse(tool) if tool else sol
        worst_hit = max(worst_hit, env.common(cam_s).Volume, env.common(ref_s).Volume)
    print('  %+5.1f deg: seat overhang %.4f  fastener/part hit %.4f'
          % (deg, worst_seat - seat_d, worst_hit - hit_d))
check(worst_seat < 1e-3, 'ワッシャ外周が全ピッチ角で母材に載っている')
check(worst_hit < 1e-3, '締結部品と工具空間が全ピッチ角で他部品と干渉しない')

# ★ rev.5 追加: 締結部品「どうし」の干渉。
#   rev.4 では他部品との干渉しか見ておらず、回転軸ボルトとクランプボルトの
#   ワッシャが 40.85 mm3 食い込んでいるのを見逃した。
print('--- fastener vs fastener ---')
_fast_pairs_ng = 0
for deg in angles:
    ang = math.radians(deg)
    cy = PIV_Y - ARC_R * math.sin(ang)
    cz = PIV_Z + ARC_R * math.cos(ang)
    sites = [('pivot', (-CHEEK_XO, PIV_Y, PIV_Z), (1, 0, 0), 2 * CHEEK_XO, True),
             ('clamp', (-CHEEK_XO, cy, cz), (1, 0, 0), 2 * CHEEK_XO, True)]
    for sx in (-1, 1):
        sites.append(('cam', (sx * M4_PITCH / 2.0, PLATE_Y0, M4_Z), (0, 1, 0),
                      PLATE_T + ENGAGE['cam'], False))
    for sx in (-1, 1):
        for sy in (-1, 1):
            sites.append(('base', (sx * FIX_X, sy * FIX_Y, BASE_Z1), (0, 0, -1),
                          BASE_T + ENGAGE['base'], False))
    solids = [fastener_shape(k, pt, d, gr, nut=nu)[0] for k, pt, d, gr, nu in sites]
    worst_pair, worst_name = 0.0, ''
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            vv = solids[i].common(solids[j]).Volume
            if vv > worst_pair:
                worst_pair, worst_name = vv, '%s(%d) x %s(%d)' % (sites[i][0], i, sites[j][0], j)
    if worst_pair > 1e-3:
        _fast_pairs_ng += 1
    print('  %+5.1f deg: 最大 %.4f mm3  %s' % (deg, worst_pair, worst_name))
check(_fast_pairs_ng == 0, '締結部品どうしが全ピッチ角で干渉しない')
check(ARC_R >= ARC_R_MIN - 1e-9,
      '円弧半径 %.2f >= 下限 %.2f (回転軸座金R %.1f + クランプ座金R %.1f + すきま %.1f)'
      % (ARC_R, ARC_R_MIN, _wp, _wc, FASTENER_CLEAR))
check(ARC_SPAN_OK, 'ピッチ振り角 ±%.0f deg >= 下限 ±%.0f deg' % (ARC_SPAN, ARC_SPAN_MIN))

# 静止側の締結部品 (カメラ / タワー) の当たり。
# めねじにねじ込む分は意図した貫入なので相手から除外し、深さで別途チェックする。
SKIP = {'cam': 'D455', 'base': 'TOWER'}
for name, (key, pt, d, grip, nut, o) in sorted(fast_objs.items()):
    for other, oshape in (('ADJUSTER', adj.Shape), ('CAM_MOUNT', cam.Shape),
                          ('TOWER', tower.Shape), ('D455', ref.Shape)):
        if SKIP.get(key) == other:
            continue
        vv = o.Shape.common(oshape).Volume
        if vv > 1e-3:
            check(False, '%s が %s と干渉 (%.2f mm3)' % (name, other, vv))
check(ENGAGE['cam'] <= 4.0, 'D455 背面へのねじ込み %.1f mm <= 4.0 mm (データシート上限)' % ENGAGE['cam'])
check(ENGAGE['base'] <= INSERT_DEPTH, 'タワーインサートへのねじ込み %.1f mm <= 下穴深さ %.1f mm'
      % (ENGAGE['base'], INSERT_DEPTH))
check(FIX_Y_OK, 'タワー取付穴の Y 縁あきが 2 mm 以上')
# カメラ背面ワッシャがプレート内に収まるか / 上端リブに当たらないか
_wcam = _f('cam', 'washer_od') / 2.0
check(M4_PITCH / 2.0 + _wcam + SEAT_MARGIN <= PLATE_HW, 'カメラ M4 ワッシャがプレート幅に収まる')
check(M4_Z + _wcam + SEAT_MARGIN <= RIB_Z0, 'カメラ M4 ワッシャが上端リブに当たらない')
check(M4_Z - _wcam - SEAT_MARGIN >= PLATE_Z0, 'カメラ M4 ワッシャがプレート下端から出ない')

print('--- clamp capacity / seat pressure ---')
m_move = CAM_MASS + cam.Shape.Volume * 1.27e-6
arm = M4_Z - PIV_Z
Fc, Fp = PRELOAD['clamp'], PRELOAD['pivot']
T_clamp = 2 * MU * Fc * ARC_R
T_pivot = 2 * MU * Fp * (FASTENERS['pivot']['washer_od'] / 2.0 + FASTENERS['pivot']['clear'] / 2.0) / 2.0
M_demand = m_move * CRASH_G * 9.81 * arm
sf = (T_clamp + T_pivot) / M_demand
print('  可動質量 %.3f kg / 腕 %.1f mm' % (m_move, arm))
print('  予圧 clamp %.0f N (%.2f N.m) / pivot %.0f N' % (Fc, FASTENERS['clamp']['torque'], Fp))
print('  保持トルク %.0f N.mm (clamp %.0f + pivot %.0f)' % (T_clamp + T_pivot, T_clamp, T_pivot))
print('  %.0f G 要求  %.0f N.mm   安全率 %.2f' % (CRASH_G, M_demand, sf))
check(sf >= 1.5, 'クランプ保持トルクの安全率 >= 1.5')

for key, area_desc, area in (
        ('clamp', 'ワッシャ座面', math.pi / 4 * (FASTENERS['clamp']['washer_od'] ** 2
                                                 - FASTENERS['clamp']['clear'] ** 2)),
        ('clamp', '頬板/タブ接触', TAB_T * 18.0),
        ('base', 'ワッシャ座面', math.pi / 4 * (FASTENERS['base']['washer_od'] ** 2
                                                - FASTENERS['base']['clear'] ** 2)),
        ('cam', 'ワッシャ座面', math.pi / 4 * (FASTENERS['cam']['washer_od'] ** 2
                                               - FASTENERS['cam']['clear'] ** 2))):
    pmpa = PRELOAD[key] / area
    print('  %-5s %-14s %6.1f mm2 -> %5.1f MPa' % (key, area_desc, area, pmpa))
    check(pmpa <= CREEP_LIMIT, '%s %s の面圧 <= %.0f MPa' % (key, area_desc, CREEP_LIMIT))

# タブ首部 (頬板上端から CAM_Z0 まで) の曲げ。ここは積層が引張を受ける向きなので
# PETG の層間強度 (20-25 MPa) で見る。断面係数 Z = TAB_W * TAB_T^2 / 6
_neck_Z = TAB_W * TAB_T ** 2 / 6.0
_neck_M = m_move * CRASH_G * 9.81 * (M4_Z - CHEEK_Z1)
_neck_s = _neck_M / _neck_Z
print('  タブ首部  断面係数 %.0f mm3  曲げ %.0f N.mm -> %.1f MPa (層間)'
      % (_neck_Z, _neck_M, _neck_s))
check(_neck_s <= 15.0, 'タブ首部の層間応力 %.1f MPa <= 15 MPa (PETG 層間 20-25 に対し余裕)' % _neck_s)

# カメラ側ねじ長さ: プレート + ワッシャ + ねじ込み(最大4)
grip_cam = PLATE_T + FASTENERS['cam']['washer_t']
print('  カメラ M4: 掴み %.1f mm + ねじ込み 3..4 mm -> ボルト長 %.1f..%.1f mm'
      % (grip_cam, grip_cam + 3.0, grip_cam + 4.0))

print('=== RESULT: %s ===' % ('ALL OK' if not NG else '%d NG' % len(NG)))
for m in NG:
    print('   NG:', m)
