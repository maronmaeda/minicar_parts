# -*- coding: utf-8 -*-
"""
JetRacer (TT-02) x Intel RealSense D455  カメラヘッドマウント
FreeCAD 0.21+ 用パラメトリックマクロ / Part ワークベンチのプリミティブ + ブーリアンのみ

rev.5  角度調整機構を廃止し、角度を印刷時に焼き込む方式にした
   - rev.3 の円弧長穴 + 摩擦保持をやめた。FDM なら角度を変えたければ刷り直す方が速く、
     摩擦継手は振動でクリープして角度が狂う。継手は丸穴4個だけ。
   - 長穴が消えたので大径ワッシャ(OD16/OD22)が不要になり、普通の M4 ワッシャで足りる。
   - タワー側の穴位置は TILT_DEG に依存しない。タワーは一度穴を開ければ、
     角度違いのヘッドを刷って差し替えるだけでよい。
   - rev.4 で踏んだ罠: 傾く枠(カメラ側)と傾かない枠(フィン)を1部品に同居させると、
     傾けた本体がフィンの内外に回り込んでボルト座面を塞ぐ。継手Yは設計角度範囲
     いっぱいまで傾けた本体の後端から実行時に導出する（derive_joint 参照）。

■ 角度の指定
    TILT_DEG に欲しい角度を入れて印刷するだけ。負 = 前下がり (nose down)。
    参考（マウント高さ 140 mm、V_FOV 57 deg のとき画角下端が地面に当たる距離）:
        0 deg -> 0.26 m      -10 deg -> 0.17 m      -20 deg -> 0.11 m
    実効 Min-Z が 0.26〜0.35 m なので、実用域はおおむね 0 〜 -10 deg。

■ 設計角度範囲を -20 〜 0 deg にしてある理由
    走行用途で前上がりは地平線より上を見るだけで使い道がない。前上がりを許すと
    背面プレートが上側で後ろへ倒れ、フィンとの結合断面が痩せる（+5 deg で 95 mm2、
    0 deg なら 200 mm2 前後）。掃引量が増えて継手も後ろへ逃がすことになる。
    範囲を広げたいときは TILT_MAX_DEG を上げれば全体が自動で追従するが、
    末尾の SELF CHECK が必ず通ることを確認すること。

■ 座標系（カメラ枠。TILT_DEG = 0 のときの姿勢で定義する）
    原点 : カメラ背面 かつ カメラ底面 かつ カメラX中心（= 光軸中心 = 1/4-20 中心線）
    X : 車両左右 (+X = 進行方向右)   0 が車両中心と一致するよう組む
    Y : 車両前後 (+Y = 前方)         カメラ本体は Y = 0 .. CAM_D を占有
    Z : 上下     (+Z = 上)           カメラ本体は Z = 0 .. CAM_H を占有
    左右フィンと継手穴だけは回転させない（= タワー枠）。ここが車体との基準になる。

■ タワー側に要求する取り合い（タワー本体はまだ未設計）
    x = +-PLATE_PITCH/2 に、X法線のパッドを2面。そこに M4 通し穴を2個ずつ。
    穴位置は実行時に出力される。設計角度範囲の中なら TILT_DEG を変えても動かない。
    ヘッドはパッドの内側に入るので、フィンが左右の壁を繋ぐシアウェブとしても働く。

■ 印刷方向
    フィンの下端面（Z = EAR_Z0 の面）をベッドに置いて立てて印刷する。
    フィンも背面プレートも垂直に近い壁になる（傾きは高々 |TILT_DEG|）。
    サポートは底面シェルフの下面のうちガセットから外れた部分だけでよい。
    層間強度はクラッシュ時 sigma = 1.5 MPa に対し PETG 層間 20 MPa で安全率13あるので、
    層方向は印刷しやすさで決めてよい。
    外周(perimeter)は 4〜5 本。FDM は外周が荷重を持つ。インフィルは 40% gyroid。

■ カメラ側の拘束（穴・長穴・平面の3点拘束）
    平面   : 背面プレート当たり面 <- カメラ背面を突き当て（Y位置とピッチ/ロール角を決める）
    Y長穴  : 底面シェルフの 1/4-20 穴 <- X位置を決める（三脚穴はカメラX中心線上にある）
    角逃がし: 背面 M4 x 2 <- 穴ピッチが未実測なので逃がしで吸収している。
             実測できれば M4_AS_HOLES = True にして丸穴にでき、ワッシャが OD22 -> OD12 になる。

■ 使い方
    FreeCAD のマクロフォルダに置いて実行。パラメータは下のブロックだけ触ればよい。
"""

import math
import os

import FreeCAD as App
import Part
from FreeCAD import Vector

# =====================================================================
# パラメータ
# =====================================================================

# --- これだけ変えれば角度が変わる ---------------------------------------
TILT_DEG = -10.0       # 負 = 前下がり。実用域は 0 〜 -10 くらい
TILT_MIN_DEG = -20.0   # 設計角度範囲。タワー側の穴位置はこの範囲で不変になる
TILT_MAX_DEG = 0.0     # 前上がりは許さない（下のコメント参照）

# --- D455 公称寸法（データシート 337029-009 Table 3-45）------------------
CAM_W = 124.0          # 全幅   公差 123.5 / 124.0 / 124.5
CAM_H = 29.0           # 全高   公差  28.5 /  29.0 /  29.5
CAM_D = 26.0           # 奥行   公差  25.5 /  26.0 /  26.5
CAM_MASS_G = 103.0     # 実測報告値。データシートに公称値の記載なし
OPTICAL_Z = 14.5       # 光軸高さ（背面高さ 29 の中央）

# --- 板厚 -------------------------------------------------------------
T_BP = 5.0             # 背面プレート厚
T_SH = 8.0             # 底面シェルフ厚
T_RIB = 5.0            # ガセット厚

# --- 背面プレート外形 --------------------------------------------------
BP_W = 140.0           # 幅。カメラ幅 124 に対し片側 8 mm ずつ張り出す
BP_Z_TOP = 34.0        # 上端（カメラ上面 +5）
BP_Z_BOT = -30.0       # 下端

# --- USB-C 逃がし窓 ----------------------------------------------------
# D455 の USB-C とシンクコネクタは背面にある。ここを塞ぐと配線できない。
# 幅は WIN_W としてフィン位置から導出する（下の「派生パラメータ」参照）。
WIN_W_MAX = 70.0       # コネクタ側から要求される幅の上限
WIN_EAR_GAP = 2.0      # 窓とフィン内側の間に残すリブ幅
WIN_Z0 = 3.0
WIN_Z1 = 27.0

# --- カメラ背面 M4 x 2 -------------------------------------------------
# 穴ピッチ未実測なので既定では角逃がしで吸収する。逃がしの上ではワッシャが宙に浮き、
# 円環面積では計算できない（OD14 だと 9.8 mm2 = 128 MPa で PETG が沈む）。
# ノギスでピッチを測れば M4_AS_HOLES = True にでき、普通のワッシャで足りるようになる。
M4_AS_HOLES = False    # True にすると M4_PITCH の丸穴になる
M4_PITCH = 100.0       # 実測値を入れる（M4_AS_HOLES = True のときだけ使う）
M4_HOLE_D = 4.5
M4_X = 50.0            # 逃がし中心のX位置（±）
M4_LEN = 24.0          # X方向長さ -> M4 ピッチ 76〜124 mm を吸収
M4_HEIGHT = 12.0       # Z方向高さ -> 上下位置 ±6 mm を吸収
M4_WASHER_OD = 22.0    # 角逃がしのとき。丸穴にできれば 12 で足りる

# --- 底面 1/4-20 ------------------------------------------------------
TRIPOD_D = 6.8
TRIPOD_Y0 = 6.0        # 長穴 始点（Y方向に伸ばす = X位置だけ拘束）
TRIPOD_Y1 = 18.0
TRIPOD_WASHER_OD = 16.0

# --- 底面シェルフ ------------------------------------------------------
SH_W = 90.0
SH_D = 22.0

# --- ヘッド <-> タワー継手（丸穴4個。角度調整機構は持たない）--------------
PLATE_PITCH = 60.0     # タワー側パッドの中心間距離 <<< 実測して要修正
JOINT_SPAN = 30.0      # 上下2本のボルトの中心間距離。曲げの受けはここで決まる
JOINT_BOLT_D = 4.3     # M4 きつめのバカ穴。摩擦ではなく穴で受ける
JOINT_WASHER_OD = 12.0 # 普通の M4 大形平ワッシャ（丸穴なので円環全面が効く）
JOINT_CLEAR = 1.0      # ワッシャ外周と、傾けた本体との最小すきま
EAR_T = 6.0            # フィン厚
EAR_EDGE = 5.0         # 穴の縁からフィン外形までの最小肉
EAR_CAM_CLEAR = 0.5    # フィン前端とカメラ外形の最小すきま

# --- ケーブルタイスロット（USB-C の応力逃がし。省くとコネクタが疲労破断する）---
TIE_W = 3.0
TIE_X = 10.0
TIE_Z0 = -22.0
TIE_Z1 = -12.0

# --- ガセット（フィンと干渉しない位置に置く）------------------------------
RIB_X = 38.0
RIB_Z_BOT = -28.0

# --- 荷重条件 ---------------------------------------------------------
CRASH_G = 64.0         # v=5 m/s を 20 mm で止めたときの減速度 a = v^2/2s
RESIN_BEARING_MAX = 10.0   # MPa。樹脂のクリープを避ける座面圧の上限

# --- 出力 -------------------------------------------------------------
EXPORT_STEP = False
EXPORT_DIR = os.path.expanduser("~")
DENSITY_G_PER_CM3 = 1.27   # PETG 固体密度
INFILL_FACTOR = 0.65       # インフィル 40% 相当の実効密度係数
SELF_CHECK = True          # 設計角度範囲の両端でも成立するか実形状で確かめる


# =====================================================================
# 派生パラメータ（形状に依存しない分）
# =====================================================================

EAR_PAD = JOINT_BOLT_D / 2.0 + EAR_EDGE     # 穴中心からフィン縁までの必要肉
EAR_X_IN = PLATE_PITCH / 2.0 - EAR_T        # フィン内側面のX
WIN_W = min(WIN_W_MAX, 2.0 * (EAR_X_IN - WIN_EAR_GAP))

# 回転中心は背面プレートの重心に置く。ここに置くと傾けたときのY方向の掃引が最小になり、
# 継手を後ろへ逃がす量（= ヘッドの奥行き）が最小になる。
ROT_Y, ROT_Z = -T_BP / 2.0, (BP_Z_TOP + BP_Z_BOT) / 2.0

JOINT_Z_HI = ROT_Z + JOINT_SPAN / 2.0
JOINT_Z_LO = ROT_Z - JOINT_SPAN / 2.0

# 形状から導出するもの（derive_joint がセットする）
JOINT_Y = None
EAR_Y0 = EAR_Y1 = None
EAR_Z0, EAR_Z1 = JOINT_Z_LO - EAR_PAD, JOINT_Z_HI + EAR_PAD


def bolt_preload(torque_nm, d_mm):
    """F = T / (0.2 d)。単位は N。"""
    return torque_nm / (0.2 * d_mm / 1000.0)


def ring_area(od, hole_d):
    """丸穴の上に載せた平ワッシャの座面積 [mm2]。円環全面が効く。"""
    return math.pi / 4.0 * (od * od - hole_d * hole_d)


def slot_bearing_area(od, slot_h):
    """高さ slot_h の長穴/角逃がしの上に載せたワッシャの実効座面積 [mm2]。

    ワッシャの円から |z| < slot_h/2 の帯（宙に浮く部分）を除いた上下2つの弓形の和。
    丸穴の円環面積とは別物で1桁小さい。取り違えると座面圧を10倍見誤る。
    """
    r, d = od / 2.0, slot_h / 2.0
    if d >= r:
        return 0.0
    return 2.0 * (r * r * math.acos(d / r) - d * math.sqrt(r * r - d * d))


def max_torque(area_mm2, d_mm, limit_mpa):
    """座面圧を limit_mpa に収めるための締付けトルク上限 [N.m]。"""
    return limit_mpa * area_mm2 * 0.2 * d_mm / 1000.0


# =====================================================================
# ヘルパ
# =====================================================================

def box(x0, x1, y0, y1, z0, z1):
    """軸平行な直方体。座標は「どこからどこまで」で指定する。"""
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, Vector(x0, y0, z0))


def cyl_z(x, y, z0, z1, d):
    return Part.makeCylinder(d / 2.0, z1 - z0, Vector(x, y, z0), Vector(0, 0, 1))


def cyl_x(y, z, x0, x1, d):
    return Part.makeCylinder(d / 2.0, x1 - x0, Vector(x0, y, z), Vector(1, 0, 0))


def slot_y(x, y0, y1, z0, z1, d):
    """Y方向に伸びた長穴（Z貫通）。X位置だけを拘束したいときに使う。"""
    s = cyl_z(x, y0, z0, z1, d).fuse(cyl_z(x, y1, z0, z1, d))
    return s.fuse(box(x - d / 2.0, x + d / 2.0, y0, y1, z0, z1))


def rib(xc, t, y_end, z_top, z_bot):
    """YZ平面内の直角三角形を X方向に t だけ押し出したガセット。"""
    p0 = Vector(xc, 0.0, z_top)
    p1 = Vector(xc, y_end, z_top)
    p2 = Vector(xc, 0.0, z_bot)
    return Part.Face(Part.makePolygon([p0, p1, p2, p0])).extrude(Vector(t, 0.0, 0.0))


def tilt(shape, deg=None):
    """カメラ枠の形状を deg だけ回してタワー枠に持ち込む。既定は TILT_DEG。"""
    s = shape.copy()
    s.rotate(Vector(0.0, ROT_Y, ROT_Z), Vector(1.0, 0.0, 0.0),
             TILT_DEG if deg is None else deg)
    return s


def sweep_ymin(shape):
    """設計角度範囲いっぱいまで傾けたとき、最も後ろに来るY。

    傾く枠の形状が、傾かないフィンの領域へどこまで回り込むかを実形状で測る。
    ここを式で近似すると角のケースを落とす（rev.4 でボルト座面を塞いだ）。
    """
    return min(tilt(shape, t).BoundBox.YMin
               for t in (TILT_MIN_DEG, 0.0, TILT_MAX_DEG))


def single_solid(shape, label):
    """OCC が Compound で返してきたら単一ソリッドを剥がす。割れていたら知らせる。"""
    if len(shape.Solids) == 1:
        return shape.Solids[0]
    App.Console.PrintError("*** %s split into %d solids. check the cuts.\n"
                           % (label, len(shape.Solids)))
    return shape


# =====================================================================
# 部品
# =====================================================================

def build_camera_side():
    """カメラ枠で作る部分。背面プレート + 底面シェルフ + ガセット。"""
    solid = box(-BP_W / 2.0, BP_W / 2.0, -T_BP, 0.0, BP_Z_BOT, BP_Z_TOP)
    solid = solid.fuse(box(-SH_W / 2.0, SH_W / 2.0, 0.0, SH_D, -T_SH, 0.0))
    for sx in (-1.0, 1.0):
        solid = solid.fuse(rib(sx * RIB_X - T_RIB / 2.0, T_RIB,
                               SH_D, -T_SH, RIB_Z_BOT))

    y0, y1 = -T_BP - 1.0, 1.0            # 背面プレートを貫く抜きのY範囲
    cuts = box(-WIN_W / 2.0, WIN_W / 2.0, y0, y1, WIN_Z0, WIN_Z1)

    for sx in (-1.0, 1.0):
        if M4_AS_HOLES:
            cuts = cuts.fuse(Part.makeCylinder(
                M4_HOLE_D / 2.0, y1 - y0,
                Vector(sx * M4_PITCH / 2.0, y0, OPTICAL_Z), Vector(0, 1, 0)))
        else:
            cx = sx * M4_X
            cuts = cuts.fuse(box(cx - M4_LEN / 2.0, cx + M4_LEN / 2.0, y0, y1,
                                 OPTICAL_Z - M4_HEIGHT / 2.0,
                                 OPTICAL_Z + M4_HEIGHT / 2.0))
        tx = sx * TIE_X
        cuts = cuts.fuse(box(tx - TIE_W / 2.0, tx + TIE_W / 2.0, y0, y1,
                             TIE_Z0, TIE_Z1))

    cuts = cuts.fuse(slot_y(0.0, TRIPOD_Y0, TRIPOD_Y1, -T_SH - 1.0, 1.0, TRIPOD_D))
    return single_solid(solid.cut(cuts), "camera side")


def camera_box():
    """カメラ外形（カメラ枠のまま。傾ける前）。"""
    return box(-CAM_W / 2.0, CAM_W / 2.0, 0.0, CAM_D, 0.0, CAM_H)


def derive_joint(cam_side):
    """継手Yとフィンの前後端を、設計角度範囲での実際の掃引から決める。

    JOINT_Y : ワッシャ外周まで含めて、傾けた本体より必ず後ろに来る位置。
              こうしないとボルト頭とナットが座る面が本体に塞がれる。
    EAR_Y1  : フィン前端。傾けたカメラ外形より必ず後ろ。フィンがカメラを突く事故を防ぐ。
    """
    global JOINT_Y, EAR_Y0, EAR_Y1
    JOINT_Y = sweep_ymin(cam_side) - JOINT_CLEAR - JOINT_WASHER_OD / 2.0
    EAR_Y1 = min(0.0, sweep_ymin(camera_box()) - EAR_CAM_CLEAR)
    EAR_Y0 = JOINT_Y - EAR_PAD


def build_ears():
    """タワー枠で作る部分。左右のフィン。回転させない。"""
    ears = None
    for sx in (-1.0, 1.0):
        xa = min(sx * PLATE_PITCH / 2.0, sx * EAR_X_IN)
        e = box(xa, xa + EAR_T, EAR_Y0, EAR_Y1, EAR_Z0, EAR_Z1)
        ears = e if ears is None else ears.fuse(e)
    return ears


def build_head(cam_side):
    """ヘッド本体。印刷するのはこれ1点だけ。"""
    solid = tilt(cam_side).fuse(build_ears())
    xw0, xw1 = -PLATE_PITCH / 2.0 - 1.0, PLATE_PITCH / 2.0 + 1.0
    holes = cyl_x(JOINT_Y, JOINT_Z_HI, xw0, xw1, JOINT_BOLT_D)
    holes = holes.fuse(cyl_x(JOINT_Y, JOINT_Z_LO, xw0, xw1, JOINT_BOLT_D))
    return single_solid(solid.cut(holes), "HEAD")


# =====================================================================
# 検査（実形状で測る。式の近似で見落とすケースを拾うため）
# =====================================================================

def check_at(deg, cam_side):
    """指定角度で作った HEAD が成立しているかを実形状で測る。"""
    global TILT_DEG
    keep, TILT_DEG = TILT_DEG, deg
    try:
        h = build_head(cam_side)
        env = tilt(camera_box())
        r = {"deg": deg,
             "solids": len(h.Solids),
             "valid": h.isValid(),
             "cam_interf": h.common(env).Volume,
             "depth": -h.BoundBox.YMin}
        # ボルト座面: フィンの内外4mmにワッシャ径ぶんの障害物が無いこと
        obst = 0.0
        for z in (JOINT_Z_HI, JOINT_Z_LO):
            for x in (EAR_X_IN - 4.0, PLATE_PITCH / 2.0):
                obst += Part.makeCylinder(JOINT_WASHER_OD / 2.0, 4.0,
                                          Vector(x, JOINT_Y, z),
                                          Vector(1, 0, 0)).common(h).Volume
        r["seat_obstruction"] = obst
        # フィンと背面プレートの結合断面（せん断で効く面積の目安）
        ear = box(EAR_X_IN, PLATE_PITCH / 2.0, EAR_Y0, EAR_Y1, EAR_Z0, EAR_Z1)
        r["merge_area"] = ear.common(tilt(cam_side)).Volume / EAR_T
        return r
    finally:
        TILT_DEG = keep


# =====================================================================
# 実行
# =====================================================================

P = App.Console.PrintMessage
E = App.Console.PrintError

if not (TILT_MIN_DEG <= TILT_DEG <= TILT_MAX_DEG):
    E("*** TILT_DEG %.1f is outside the design range %.1f .. %.1f\n"
      % (TILT_DEG, TILT_MIN_DEG, TILT_MAX_DEG))

cam_side = build_camera_side()
derive_joint(cam_side)

doc = App.newDocument("D455_HeadMount")
head_shape = build_head(cam_side)
head = doc.addObject("Part::Feature", "HEAD")
head.Shape = head_shape

env = doc.addObject("Part::Feature", "CameraEnvelope_REF")
env.Shape = tilt(camera_box())
if hasattr(env, "ViewObject"):
    env.ViewObject.Transparency = 75
doc.recompute()

# --- 質量と重心 --------------------------------------------------------
m_head = head_shape.Volume / 1000.0 * DENSITY_G_PER_CM3 * INFILL_FACTOR
c_h, c_c = head_shape.CenterOfMass, env.Shape.CenterOfMass
m_tot = m_head + CAM_MASS_G
cg_y = (m_head * c_h.y + CAM_MASS_G * c_c.y) / m_tot
cg_z = (m_head * c_h.z + CAM_MASS_G * c_c.z) / m_tot

P("tilt %+.1f deg (negative = nose down), design range %+.0f .. %+.0f deg\n"
  % (TILT_DEG, TILT_MIN_DEG, TILT_MAX_DEG))
P("HEAD      volume %6.1f cm3   est. mass %5.1f g   (printed parts: 1)\n"
  % (head_shape.Volume / 1000.0, m_head))
P("with camera         : %.1f g   CG at y=%.1f z=%.1f\n" % (m_tot, cg_y, cg_z))
P("head depth behind the camera rear face : %.1f mm\n" % -head_shape.BoundBox.YMin)
P("-" * 70 + "\n")

# --- 検算 1 : USB-C 窓がフィンを食っていないか --------------------------
P("USB-C window   : %.1f mm wide%s\n" % (
    WIN_W, "" if WIN_W >= WIN_W_MAX
    else "  <- clamped from %.0f by PLATE_PITCH=%.0f (measure #1, then re-check USB-C fit)"
         % (WIN_W_MAX, PLATE_PITCH)))
if WIN_W / 2.0 > EAR_X_IN:
    E("  *** window overruns the ears by %.1f mm\n" % (WIN_W / 2.0 - EAR_X_IN))

# --- 検算 2 : ワッシャ座面圧と締付けトルク上限 ---------------------------
P("\n--- bearing stress under each washer (limit %.0f MPa) ---\n" % RESIN_BEARING_MAX)
if M4_AS_HOLES:
    _a4, _kind = ring_area(M4_WASHER_OD, M4_HOLE_D), "round hole"
else:
    _a4, _kind = slot_bearing_area(M4_WASHER_OD, M4_HEIGHT), "%.0f mm slot" % M4_HEIGHT
for name, od, area, dia in (
        ("camera M4  (%s)" % _kind, M4_WASHER_OD, _a4, 4.0),
        ("joint  M4  (round hole)", JOINT_WASHER_OD,
         ring_area(JOINT_WASHER_OD, JOINT_BOLT_D), 4.0),
        ("camera 1/4-20 (slot)", TRIPOD_WASHER_OD,
         slot_bearing_area(TRIPOD_WASHER_OD, TRIPOD_D), 6.35)):
    P("  %-26s OD%-5.0f area %6.1f mm2   max torque %.2f N.m\n"
      % (name, od, area, max_torque(area, dia, RESIN_BEARING_MAX)))
if not M4_AS_HOLES:
    P("  -> measure the camera M4 pitch (#6) and set M4_AS_HOLES = True:\n"
      "     the OD22 fender washer becomes a plain OD12 one (%.0f -> %.0f mm2)\n"
      % (_a4, ring_area(12.0, M4_HOLE_D)))

# --- 検算 3 : 継手ボルトの荷重 ------------------------------------------
_f = m_tot / 1000.0 * CRASH_G * 9.81
_arm = math.hypot(cg_y - JOINT_Y, cg_z - ROT_Z)
_m = _f * _arm / 1000.0
P("\n--- joint at %.0f G ---\n" % CRASH_G)
P("  inertia %.0f N, arm %.1f mm -> moment %.2f N.m\n" % (_f, _arm, _m))
P("  per bolt: tension %.0f N, shear %.0f N, hole bearing %.1f MPa\n"
  % (_m / (JOINT_SPAN / 1000.0) / 2.0, _f / 4.0,
     (_f / 4.0) / (JOINT_BOLT_D * EAR_T)))

# --- SELF CHECK : 設計角度範囲の両端でも成立するか ------------------------
if SELF_CHECK:
    P("\n--- SELF CHECK across the design range (measured on the real solids) ---\n")
    P("   deg  solids valid  cam interf  seat obstr  ear-plate merge   depth\n")
    bad = False
    for t in (TILT_MIN_DEG, TILT_DEG, TILT_MAX_DEG):
        r = check_at(t, cam_side)
        ng = (r["solids"] != 1 or not r["valid"] or r["cam_interf"] > 1e-6
              or r["seat_obstruction"] > 1e-6 or r["merge_area"] < 100.0)
        bad = bad or ng
        P("  %+5.1f    %d    %-5s %9.3f mm3 %9.3f mm3 %11.0f mm2 %6.1f mm%s\n"
          % (t, r["solids"], r["valid"], r["cam_interf"], r["seat_obstruction"],
             r["merge_area"], r["depth"], "   <-- NG" if ng else ""))
    P("  (merge = ear-to-backplate shear section. keep it above ~100 mm2)\n")
    if bad:
        E("*** self check failed. narrow TILT_MIN/MAX_DEG or increase JOINT_CLEAR.\n")

# --- タワー側の取り合い ------------------------------------------------
P("""
--- tower interface (fixed over the whole design range) ----------------
  two X-normal pads at x = +-%.1f
  M4 through holes, 2 per pad :  (y, z) = (%.2f, %.2f)
                                 (y, z) = (%.2f, %.2f)
  the head sits between the pads, so the ears also tie the two walls together
-----------------------------------------------------------------------

--- hardware (printed parts: HEAD only) -------------------------------
  M4 x 12                  x2   camera rear      washer OD%.0f
  1/4-20 x 12              x1   camera bottom    washer OD%.0f
  M4 x 30 + nyloc nut      x4   head <-> tower   washer OD%.0f both sides
  cable tie 2.5 mm         x1   USB-C strain relief
  butyl 1 mm               ---  camera rear seating face
  * retighten the day after assembly and after the first run (resin creeps)
  * to change the angle: edit TILT_DEG and reprint. the tower stays as is.
-----------------------------------------------------------------------
""" % (PLATE_PITCH / 2.0, JOINT_Y, JOINT_Z_HI, JOINT_Y, JOINT_Z_LO,
       M4_WASHER_OD, TRIPOD_WASHER_OD, JOINT_WASHER_OD))

if EXPORT_STEP:
    p = os.path.join(EXPORT_DIR, "d455_head_tilt%+.0f.step" % TILT_DEG)
    Part.export([head], p)
    P("exported: %s\n" % p)
