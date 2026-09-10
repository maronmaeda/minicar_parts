# -*- coding: utf-8 -*-
"""
ASSEMBLY.FCStd — App::Link による「生きた」組立ファイル
==========================================================
parts/0X_*.FCStd の Body を **外部リンク** で参照する組立。
部品ファイル側で寸法を編集して保存すると、この組立の表示が自動で追従する。

  運用 (B): 部品ファイルを正とする
    1. parts/02_ADJUSTER.FCStd などを FreeCAD の GUI で開いてスケッチを編集
    2. 保存 (Ctrl+S)
    3. ASSEMBLY.FCStd 側が自動で更新される
       (同時に開いていれば即時。閉じていれば次に開いたとき)

ピッチ角は App::Part コンテナ "PITCH" の Placement で与える。
コンテナの原点が回転軸 (0, PIV_Y, PIV_Z) に置いてあるので、
プロパティエディタで Angle を変えるだけで軸まわりに正しく回る。
マクロからは set_pitch(-12) のように呼べる。

ツリー構成:
  ASSEMBLY
   ├ TOWER          -> parts/01_TOWER.FCStd    の Body     (静止)
   ├ ADJUSTER       -> parts/02_ADJUSTER.FCStd の Body     (静止)
   ├ REF_BoltPivot / REF_BoltBase*             (静止)
   └ PITCH  (App::Part / 原点 = 回転軸)
      ├ CAM_MOUNT   -> parts/03_CAM_MOUNT.FCStd の Body    (回る)
      ├ REF_D455                                           (回る)
      └ REF_BoltClamp / REF_BoltCamL / REF_BoltCamR        (回る)

注意:
- リンクは「部品ファイルの Body」を指す。部品ファイルを移動・改名しないこと
- REF_ (D455 外形・締結部品) は静的な参考形状。部品側で穴位置を動かしたら
  jetracer_d455_mount.FCMacro.py を回して作り直すこと
- 外部リンクなので、ASSEMBLY を開くと参照先の部品ファイルも一緒に開かれる
"""

import os
import FreeCAD as App

try:
    import FreeCADGui as Gui
    HAS_GUI = App.GuiUp
except Exception:
    HAS_GUI = False

ROOT = r"C:\Users\user\Documents\Free_cad"
PARTS_DIR = os.path.join(ROOT, "parts")
ASM_PATH = os.path.join(ROOT, "ASSEMBLY.FCStd")

# 回転軸。ハードコードせず 02_ADJUSTER.FCStd の Sk_A5_PivotArc の円から読む
PIV_Y, PIV_Z = 4.0, 120.0          # _load_pivot() が上書きする

# ★ 一体版 (04_TOWER_ADJ) と分割版 (01+02) のどちらで組むかを選ぶ。
#   両方の部品ファイルは残してあるので、ここを切り替えるだけで組み替えられる。
MERGED = True

PART_FILES_MERGED = {
    'TOWER_ADJ': '04_TOWER_ADJ.FCStd',
    'CAM_MOUNT': '03_CAM_MOUNT.FCStd',
}
PART_FILES_SPLIT = {
    'TOWER':     '01_TOWER.FCStd',
    'ADJUSTER':  '02_ADJUSTER.FCStd',
    'CAM_MOUNT': '03_CAM_MOUNT.FCStd',
}
PART_FILES = PART_FILES_MERGED if MERGED else PART_FILES_SPLIT
# 静止側 (ピッチ回転しない) の部品
STATIC = ('TOWER_ADJ',) if MERGED else ('TOWER', 'ADJUSTER')
# 参照ソリッド (D455 とボルト) をどの部品ファイルから借りてくるか
REF_SRC = 'TOWER_ADJ' if MERGED else 'ADJUSTER'

COL = {'TOWER': (0.55, 0.55, 0.58), 'ADJUSTER': (0.95, 0.55, 0.10),
       'TOWER_ADJ': (0.80, 0.45, 0.15), 'CAM_MOUNT': (0.20, 0.55, 0.90)}
COL_REF = (0.20, 0.80, 0.35)
COL_BOLT = (0.85, 0.15, 0.15)

# PITCH コンテナに入れる = 回転に追従するもの
ROTATING = ('REF_D455', 'REF_BoltClamp', 'REF_BoltCamL', 'REF_BoltCamR')


def _open(fname):
    path = os.path.join(PARTS_DIR, fname)
    for d in App.listDocuments().values():
        if d.FileName and os.path.normcase(d.FileName) == os.path.normcase(path):
            return d
    return App.openDocument(path)


def _body(doc):
    for o in doc.Objects:
        if o.TypeId == 'PartDesign::Body':
            return o
    raise RuntimeError('body not found in ' + doc.Label)


def _view(obj, rgb, transp=0):
    """App::Link の ViewProviderLink には ShapeColor が無く、
    OverrideMaterial + ShapeMaterial で色を上書きする。
    何も指定しなければリンク先の色をそのまま継承するので、失敗しても実害はない。"""
    if not HAS_GUI:
        return
    vo = getattr(obj, 'ViewObject', None)
    if vo is None:
        return
    try:
        if hasattr(vo, 'ShapeColor'):
            vo.ShapeColor = rgb
            vo.Transparency = transp
        elif hasattr(vo, 'ShapeMaterial'):
            m = vo.ShapeMaterial
            m.DiffuseColor = rgb
            m.Transparency = transp / 100.0
            vo.ShapeMaterial = m
            vo.OverrideMaterial = True
    except Exception as e:
        print('  (view) %s: %s' % (getattr(obj, 'Name', '?'), e))


def _load_pivot():
    """回転軸を 02_ADJUSTER.FCStd の Sk_A5_PivotArc から読んで PIV_Y/PIV_Z を更新する。
    寸法を変えても組立側が勝手に追従するようにするため、値をコードに埋めない。"""
    global PIV_Y, PIV_Z
    d = _open(PART_FILES[REF_SRC])
    a5 = d.getObject('Sk_A5_PivotArc')
    if a5 is None:
        return PIV_Y, PIV_Z
    cir = [g for g in a5.Geometry if g.TypeId == 'Part::GeomCircle'][0]
    PIV_Y, PIV_Z = cir.Center.x, cir.Center.y
    return PIV_Y, PIV_Z


def build():
    parts = {k: _open(v) for k, v in PART_FILES.items()}
    _load_pivot()
    print('  pivot = (0, %.4f, %.4f)' % (PIV_Y, PIV_Z))

    # 既存の ASSEMBLY は閉じてから作り直す
    for d in list(App.listDocuments().values()):
        if d.FileName and os.path.normcase(d.FileName) == os.path.normcase(ASM_PATH):
            App.closeDocument(d.Name)
    for d in list(App.listDocuments().values()):
        if d.Name == 'ASSEMBLY' and not d.FileName:
            App.closeDocument(d.Name)
    asm = App.newDocument('ASSEMBLY')
    # ★ 外部リンクは相対パスを解決する必要があるので、
    #   リンクを張る前に組立ドキュメントを一度保存しておかなければならない
    asm.saveAs(ASM_PATH)

    def link(name, target, label=None):
        lk = asm.addObject('App::Link', name)
        lk.LinkedObject = target
        if lk.LinkedObject is None:
            raise RuntimeError('外部リンクを張れなかった: %s -> %s (%s)'
                               % (name, target.Name, target.Document.Label))
        # ★ LinkTransform=False (既定) だとリンク先自身の Placement を「置き換えて」しまう。
        #   参照ソリッドは絶対座標の Placement を持っているので、必ず True にして
        #   リンク先の配置を保ったまま親コンテナの変換だけを重ねる。
        lk.LinkTransform = True
        lk.Label = label or name
        return lk

    made = {}
    # --- 静止側 -------------------------------------------------------
    for key in STATIC:
        lk = link(key, _body(parts[key]))
        _view(lk, COL[key])
        made[key] = lk

    # 参照物は REF_SRC の部品ファイルに入っているものをリンクで持ってくる
    src_ref = parts[REF_SRC]
    static_refs = [o for o in src_ref.Objects
                   if o.Name.startswith('REF_Bolt') and o.Name not in ROTATING]
    for o in static_refs:
        lk = link(o.Name, o, o.Label)
        _view(lk, COL_BOLT, 20)

    # --- ピッチ回転側 -------------------------------------------------
    # 二段のコンテナにする。
    #   PITCH       : 原点を回転軸に置き、Placement の Angle がそのままピッチ角になる
    #   PITCH_LOCAL : 回転軸ぶん戻すだけ。これで中のリンクは Placement を触らなくてよい
    pitch = asm.addObject('App::Part', 'PITCH')
    pitch.Label = 'PITCH_ピッチ角'
    pitch.Placement = App.Placement(App.Vector(0, PIV_Y, PIV_Z),
                                    App.Rotation(App.Vector(1, 0, 0), 0))
    local = asm.addObject('App::Part', 'PITCH_LOCAL')
    local.Label = 'PITCH_LOCAL_軸オフセット'
    local.Placement = App.Placement(App.Vector(0, -PIV_Y, -PIV_Z), App.Rotation())
    pitch.addObject(local)

    cam = link('CAM_MOUNT', _body(parts['CAM_MOUNT']))
    _view(cam, COL['CAM_MOUNT'])
    local.addObject(cam)
    made['CAM_MOUNT'] = cam

    for nm in ROTATING:
        o = src_ref.getObject(nm)
        if o is None:
            continue
        lk = link(nm, o, o.Label)
        _view(lk, COL_REF if nm == 'REF_D455' else COL_BOLT,
              70 if nm == 'REF_D455' else 20)
        local.addObject(lk)

    asm.recompute()
    asm.save()
    print('built:', ASM_PATH)
    ng = 0
    for k, lk in sorted(made.items()):
        src_vol = _body(parts[k]).Shape.Volume
        ok = abs(lk.Shape.Volume - src_vol) < 1e-3
        ng += 0 if ok else 1
        print('  [%s] %-10s -> %-14s link=%9.1f  part=%9.1f'
              % ('OK' if ok else 'NG', k, lk.LinkedObject.Document.Label,
                 lk.Shape.Volume, src_vol))
    try:
        ng += verify(asm)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('  (verify) 例外:', e)
        ng += 1
    print('=== %s ===' % ('ALL OK' if ng == 0 else '%d NG' % ng))
    return asm


def _cog(shape):
    """体積重み付き重心。Compound には CenterOfMass が無いのでソリッドから求める。"""
    tot, acc = 0.0, App.Vector(0, 0, 0)
    for s in shape.Solids:
        tot += s.Volume
        acc = acc.add(s.CenterOfMass.multiply(s.Volume))
    return acc.multiply(1.0 / tot) if tot else App.Vector(0, 0, 0)


def _ancestor_placement(obj):
    """App::Part コンテナの入れ子を遡って Placement を合成する。
    App::Link には getGlobalPlacement が無いので自前で辿る。"""
    pl = App.Placement()
    cur, seen = obj, set()
    while True:
        parent = None
        for q in cur.InList:
            if q.TypeId == 'App::Part' and cur in q.Group:
                parent = q
                break
        if parent is None or parent.Name in seen:
            break
        seen.add(parent.Name)
        pl = parent.Placement.multiply(pl)
        cur = parent
    return pl


def global_shape(lk):
    """コンテナの入れ子を含めた、リンクの絶対座標での形状。
    lk.Shape は「リンク自身の Placement + LinkTransform」までは含むが、
    親コンテナの変換は含まないので、ここで重ねる。"""
    sh = lk.Shape.copy()
    sh.Placement = _ancestor_placement(lk).multiply(sh.Placement)
    return sh


def verify(asm=None, master='Unnamed'):
    """ピッチ 0 deg のとき、マクロ生成のアセンブリ (タワー.FCStd) と
    同じ位置・同じ体積になっているかを照合する。"""
    asm = asm or _asm()
    _load_pivot()
    # マスターは開き直すと内部名が変わる (Unnamed -> タワー) ので FileName でも探す
    m = App.listDocuments().get(master)
    if m is None:
        mp = os.path.join(ROOT, 'タワー.FCStd')
        for c in App.listDocuments().values():
            if c.FileName and os.path.normcase(c.FileName) == os.path.normcase(mp):
                m = c
                break
    if m is None:
        print('  (verify) マスター (タワー.FCStd) が開いていないので位置照合はスキップ')
        return 0
    pitch = asm.getObject('PITCH')
    keep = pitch.Placement
    pitch.Placement = App.Placement(App.Vector(0, PIV_Y, PIV_Z),
                                    App.Rotation(App.Vector(1, 0, 0), 0))
    asm.recompute()
    pairs = [('TOWER', 'Body'), ('ADJUSTER', 'ADJUSTER'),
             ('CAM_MOUNT', 'CAM_MOUNT'), ('REF_D455', 'D455_REF')]
    # 一体版の TOWER_ADJ はマスターに対応物が無いので位置照合はスキップされる
    # (形状の一致は merge_tower_adjuster.FCMacro.py 側で確認済み)
    pairs += [(o.Name, o.Name) for o in asm.Objects if o.Name.startswith('REF_Bolt')]
    ng = 0
    print('  -- position check vs %s (pitch 0 deg) --' % master)
    for ln, mn in pairs:
        lk, mo = asm.getObject(ln), m.getObject(mn)
        if lk is None or mo is None:
            continue
        gs = global_shape(lk)
        a_bb, b_bb = gs.BoundBox, mo.Shape.BoundBox
        d = max(abs(a_bb.XMin - b_bb.XMin), abs(a_bb.YMin - b_bb.YMin),
                abs(a_bb.ZMin - b_bb.ZMin), abs(a_bb.XMax - b_bb.XMax),
                abs(a_bb.YMax - b_bb.YMax), abs(a_bb.ZMax - b_bb.ZMax))
        # 位置の一致は重心と体積で判定する。曲面のバウンディングボックスは
        # テセレーション精度で 0.05 mm ほど揺れるので BB は参考値 (0.1 mm 許容)
        cg = _cog(gs).sub(_cog(mo.Shape)).Length
        dv = abs(gs.Volume - mo.Shape.Volume)
        ok = d < 0.1 and cg < 1e-4 and dv < 1e-3
        ng += 0 if ok else 1
        print('     [%s] %-16s BB %.4f mm / 重心 %.6f mm / 体積差 %.6f mm3'
              % ('OK' if ok else 'NG', ln, d, cg, dv))
    pitch.Placement = keep
    asm.recompute()
    return ng


def _asm():
    for d in App.listDocuments().values():
        if d.FileName and os.path.normcase(d.FileName) == os.path.normcase(ASM_PATH):
            return d
    return App.openDocument(ASM_PATH)


def set_pitch(deg):
    """ピッチ角を与える。負角 = 前傾 (見下ろし)。"""
    _load_pivot()
    a = _asm()
    p = a.getObject('PITCH')
    p.Placement = App.Placement(App.Vector(0, PIV_Y, PIV_Z),
                                App.Rotation(App.Vector(1, 0, 0), deg))
    a.recompute()
    print('pitch = %+.1f deg' % deg)
    return p


def refresh():
    """部品ファイルを編集したあと、組立を明示的に再計算する。
    (GUI で部品を保存すれば普通は自動で追従するが、念のため)"""
    for k, v in PART_FILES.items():
        d = _open(v)
        d.recompute()
    a = _asm()
    a.recompute()
    print('refreshed. volumes:')
    for nm in ('TOWER', 'ADJUSTER', 'CAM_MOUNT'):
        o = a.getObject(nm)
        if o:
            print('  %-10s %9.1f mm3' % (nm, o.Shape.Volume))
    return a


if __name__ == '__main__':
    build()
