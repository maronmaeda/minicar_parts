# -*- coding: utf-8 -*-
"""
04_TOWER_ADJ.FCStd — タワーとピッチ調整ヨークの「一体版」を作る
==============================================================
parts/01_TOWER.FCStd のタワー本体と parts/02_ADJUSTER.FCStd のヨークを、
**1つの PartDesign Body** として合成した部品ファイルを出力する。

  01_TOWER + 02_ADJUSTER  ->  04_TOWER_ADJ   (M3 x 4 の締結が不要になる)

分割版 (01 / 02) はそのまま残す。アセンブリはどちらを使ってもよい。

一体化して得るもの:
  - M3 x 4 と熱圧入インサート x 4 が不要 (部品点数・組付け・増し締めが減る)
  - ベース板の座面 (9.2 MPa) というクリープ源が消える
  - 継手が 1 つ減るぶん系の固有振動数が上がる

一体化で失うもの:
  - タワーを作り直すとヨークも一緒に再印刷になる
  - ベース板とタワー上面の間にシムを挟む逃げ道がなくなる

寸法は 01 / 02 の**スケッチをそのまま流用**する。
つまり分割版で寸法を変えれば、この macro を回し直すだけで一体版も追従する。
パラメータをここに書き写していないので、二重管理にならない。

CAM_MOUNT (03) は分割版・一体版で共通。ヨークの寸法を触っていないので、
どちらの組み合わせでも同じものが使える。

print 姿勢: タワー底面をベッドに置いて立てる。
  - コの字スロットの天井 36 mm はブリッジ (分割版のタワー単体でも同じ)
  - 頬板は +Z に立ち上がるだけなのでサポート不要
  - 円弧長穴と回転軸穴は縦壁の横穴なので 4.5-5.5 mm のブリッジ
"""

import os
import datetime
import shutil
import FreeCAD as App

try:
    import FreeCADGui as Gui
    HAS_GUI = App.GuiUp
except Exception:
    HAS_GUI = False

ROOT = r"C:\Users\user\Documents\Free_cad"
PARTS_DIR = os.path.join(ROOT, "parts")
BACKUP_DIR = os.path.join(PARTS_DIR, "_backup")

SRC_TOWER = "01_TOWER.FCStd"
SRC_ADJ = "02_ADJUSTER.FCStd"
SRC_CAM = "03_CAM_MOUNT.FCStd"
OUT = "04_TOWER_ADJ.FCStd"

# 02_ADJUSTER のうち一体版では使わないフィーチャ (タワーへの M3 締結穴)
SKIP_FEATURES = ('Pocket_A4_FixHoles',)
# 01_TOWER のうち一体版では使わないフィーチャ (M3 熱圧入インサートの下穴)
DROP_TOWER = ('Pocket_TowerInserts', 'Sketch_TowerInserts')

COL_MERGED = (0.80, 0.45, 0.15)
COL_REF = (0.65, 0.65, 0.65)
COL_BOLT = (0.85, 0.15, 0.15)


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
    if not HAS_GUI:
        return
    try:
        obj.ViewObject.ShapeColor = rgb
        obj.ViewObject.Transparency = transp
    except Exception:
        pass


def backup(path):
    if not os.path.exists(path):
        return None
    if not os.path.isdir(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    dst = os.path.join(BACKUP_DIR,
                       os.path.basename(path).replace('.FCStd', '.%s.FCStd' % stamp))
    shutil.copy2(path, dst)
    return dst


def _origin_plane(body, role):
    for f in body.Origin.OriginFeatures:
        if f.Role == role:
            return f
    raise RuntimeError('origin plane not found: ' + role)


def _plane_role(sk):
    """スケッチが XY / XZ / YZ のどれに付いているかを Role で返す。"""
    sup = sk.AttachmentSupport
    if not sup:
        return None
    return getattr(sup[0][0], 'Role', None)


def build():
    tdoc, adoc = _open(SRC_TOWER), _open(SRC_ADJ)
    tbody, abody = _body(tdoc), _body(adoc)
    path = os.path.join(PARTS_DIR, OUT)
    bak = backup(path)
    if bak:
        print('  backup ->', os.path.relpath(bak, ROOT))
    for d in list(App.listDocuments().values()):
        if d.FileName and os.path.normcase(d.FileName) == os.path.normcase(path):
            App.closeDocument(d.Name)

    nd = App.newDocument('04_TOWER_ADJ')

    # --- 1) タワー本体を履歴ごとコピー ---------------------------------
    body = nd.copyObject(tbody, True)
    body.Label = 'TOWER_ADJ_一体版'
    nd.recompute()
    # インサート下穴は一体版では不要なので落とす (Label で引き当てる)
    for o in list(body.Group):
        if any(o.Label.startswith(n) for n in DROP_TOWER):
            try:
                nd.removeObject(o.Name)
            except Exception as e:
                print('   drop skip', o.Label, e)
    nd.recompute()
    print('  tower copied: vol=%.1f  BB=%s' % (body.Shape.Volume, body.Shape.BoundBox))

    # --- 2) ヨークのフィーチャを 02 から順番に移植 ----------------------
    #     スケッチは 02 のものをそのままコピーし、Pad/Pocket のパラメータも
    #     02 の値をそのまま読んで再現する (寸法をここに書き写さない)
    n_moved = 0
    for feat in abody.Group:
        if feat.TypeId not in ('PartDesign::Pad', 'PartDesign::Pocket'):
            continue
        if feat.Name in SKIP_FEATURES:
            print('  skip  %-22s (一体版では不要)' % feat.Name)
            continue
        src_sk = feat.Profile[0] if isinstance(feat.Profile, (list, tuple)) else feat.Profile
        role = _plane_role(src_sk)
        if role is None:
            print('  skip  %-22s (アタッチ先が原点平面でない)' % feat.Name)
            continue

        # スケッチを新規に作り、02 のジオメトリと拘束をそのまま入れる
        sk = nd.addObject('Sketcher::SketchObject', src_sk.Name)
        body.addObject(sk)
        sk.AttachmentSupport = [(_origin_plane(body, role), '')]
        sk.MapMode = 'FlatFace'
        sk.AttachmentOffset = src_sk.AttachmentOffset
        for i, gm in enumerate(src_sk.Geometry):
            sk.addGeometry(gm, src_sk.getConstruction(i))
        for c in src_sk.Constraints:
            sk.addConstraint(c)
        sk.solve()

        f = nd.addObject(feat.TypeId, feat.Name)
        body.addObject(f)
        f.Profile = sk
        # ★ FreeCAD 1.1 では対称押し出しの実体は 'SideType'
        #   ('One side' / 'Two sides' / 'Symmetric')。旧 'Midplane' は
        #   書き込みには効くが読み出すと常に False を返す。
        #   したがって Midplane は「コピーしてはいけない」。
        #   SideType の後に Midplane=False を書くと SideType が
        #   'One side' に戻され、片側だけ伸びた形になる。
        for prop in ('Type', 'SideType', 'Length', 'Length2',
                     'Reversed', 'Offset'):
            if hasattr(feat, prop) and hasattr(f, prop):
                setattr(f, prop, getattr(feat, prop))
        nd.recompute()
        ok = 'Invalid' not in (f.State or [])
        print('  move  %-22s %-20s len=%-8s -> %s  DoF=%d'
              % (feat.Name, feat.TypeId.split('::')[-1],
                 getattr(f, 'Length', '-'), 'OK' if ok else 'INVALID', sk.DoF))
        n_moved += 1

    nd.recompute()
    _view(body, COL_MERGED)

    # --- 3) 参照ソリッド (CAM_MOUNT / D455 / ボルト) ---------------------
    cdoc = _open(SRC_CAM)
    for o in cdoc.Objects:
        if o.TypeId == 'PartDesign::Body':
            r = nd.addObject('Part::Feature', 'REF_CAM_MOUNT')
            r.Label = 'REF_CAM_MOUNT_参照_印刷対象外'
            r.Shape = o.Shape.copy()
            _view(r, COL_REF, 75)
        elif o.Name == 'REF_D455':
            r = nd.addObject('Part::Feature', 'REF_D455')
            r.Label = o.Label
            r.Shape = o.Shape.copy()
            _view(r, COL_REF, 75)
    # 一体版で残る締結部品だけ (タワー固定 M3 x4 は不要になったので除く)
    for o in adoc.Objects:
        if o.Name.startswith('REF_Bolt') and 'Base' not in o.Name:
            r = nd.addObject('Part::Feature', o.Name)
            r.Label = o.Label
            r.Shape = o.Shape.copy()
            _view(r, COL_BOLT, 20)

    nd.Comment = ('01_TOWER.FCStd と 02_ADJUSTER.FCStd を merge_tower_adjuster.FCMacro.py で'
                  '合成した一体版。分割版で寸法を変えたらこの macro を回し直すこと。'
                  'REF_ で始まるものは参照用で印刷対象外。')
    nd.recompute()
    nd.saveAs(path)

    # --- 4) 検証 --------------------------------------------------------
    s = body.Shape
    tv, av = tbody.Shape.Volume, abody.Shape.Volume
    fix_holes = 4 * 3.14159265 * (3.4 / 2.0) ** 2 * 17.0     # 分割版ベースの M3 バカ穴
    inserts = 4 * 3.14159265 * (4.2 / 2.0) ** 2 * 8.0        # タワーのインサート下穴
    expect = tv + av + fix_holes + inserts
    print('--- merged ---')
    print('  solids=%d  valid=%s  vol=%.1f mm3  mass(PETG)=%.1f g'
          % (len(s.Solids), s.isValid(), s.Volume, s.Volume * 1.27e-3))
    print('  BB=%s' % s.BoundBox)
    print('  分割版の合計 %.1f + 締結穴ぶん %.1f = %.1f  (差 %.1f)'
          % (tv + av, fix_holes + inserts, expect, s.Volume - expect))
    n_sk = len([o for o in body.Group if o.TypeId == 'Sketcher::SketchObject'])
    n_fc = len([o for o in body.Group
                if o.TypeId == 'Sketcher::SketchObject' and o.FullyConstrained])
    print('  sketches=%d (fully constrained %d)  features moved=%d' % (n_sk, n_fc, n_moved))
    ng = []
    if len(s.Solids) != 1:
        ng.append('単一ソリッドでない (%d)' % len(s.Solids))
    if not s.isValid():
        ng.append('形状が invalid')
    if n_fc != n_sk:
        ng.append('未拘束のスケッチがある (%d/%d)' % (n_fc, n_sk))
    # 分割版と外形が一致しているか
    import Part
    fused = tbody.Shape.fuse(abody.Shape).removeSplitter()
    bb1, bb2 = s.BoundBox, fused.BoundBox
    d = max(abs(bb1.XMin - bb2.XMin), abs(bb1.YMin - bb2.YMin), abs(bb1.ZMin - bb2.ZMin),
            abs(bb1.XMax - bb2.XMax), abs(bb1.YMax - bb2.YMax), abs(bb1.ZMax - bb2.ZMax))
    print('  分割版を fuse したものとの BB ずれ = %.4f mm' % d)
    if d > 0.05:
        ng.append('分割版と外形が一致しない (%.3f mm)' % d)
    print('=== %s ===' % ('ALL OK' if not ng else 'NG: ' + ' / '.join(ng)))
    print('saved:', path)
    return nd


if __name__ == '__main__':
    print('--- merge tower + adjuster ---')
    build()
