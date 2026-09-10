# -*- coding: utf-8 -*-
"""
アセンブリ (タワー.FCStd) を部品単位の FCStd に切り出す。

  parts/01_TOWER.FCStd       ... 既存タワー本体
  parts/02_ADJUSTER.FCStd    ... ピッチ角調整ヨーク
  parts/03_CAM_MOUNT.FCStd   ... D455 固定治具

各ファイルには
  - その部品の PartDesign Body 一式 (スケッチ・パッド・ポケットの履歴をそのまま)
  - 相手部品と D455 の「参照ソリッド」(Part::Feature / 半透明 / 編集不可の板状データ)
が入る。参照は当たりを見るためだけのもので、印刷対象ではない。

座標系はアセンブリと共通 (原点 = タワー底面の中心、タワー上面 Z=100)。
部品ファイル側で寸法を変えてもアセンブリには自動で戻らない。
運用は次のどちらかに決めること:

  (A) マクロを正とする  … jetracer_d455_mount.FCMacro.py の PARAMETERS を編集
                          → 再実行 → この split を再実行。部品ファイルは毎回作り直し
  (B) 部品ファイルを正とする … 部品ファイルで直接スケッチを編集。
                          アセンブリでの当たり確認は check_fit() を使う

既存の部品ファイルは parts/_backup/ にタイムスタンプ付きで退避してから上書きする。
"""

import os
import datetime
import shutil
import FreeCAD as App
import Part

try:
    import FreeCADGui as Gui
    HAS_GUI = App.GuiUp
except Exception:
    HAS_GUI = False

SRC_DOC = "Unnamed"                     # ラベル「タワー」のアセンブリ
# 開き直すと内部名が変わる (Unnamed -> タワー) ので FileName で引き当てる
def _master():
    d = App.listDocuments().get(SRC_DOC)
    if d is not None:
        return d
    path = os.path.join(ROOT, "\u30bf\u30ef\u30fc.FCStd")
    for c in App.listDocuments().values():
        if c.FileName and os.path.normcase(c.FileName) == os.path.normcase(path):
            return c
    return App.openDocument(path)

ROOT = r"C:\Users\user\Documents\Free_cad"
PARTS_DIR = os.path.join(ROOT, "parts")
BACKUP_DIR = os.path.join(PARTS_DIR, "_backup")

COL = {
    'Body':      (0.55, 0.55, 0.58),
    'ADJUSTER':  (0.95, 0.55, 0.10),
    'CAM_MOUNT': (0.20, 0.55, 0.90),
}
COL_REF = (0.65, 0.65, 0.65)
COL_BOLT = (0.85, 0.15, 0.15)
REF_TRANSP = 75

# 出力する部品: (アセンブリ内の名前, 出力ファイル名, ラベル)
PARTS = [
    ('Body',      '01_TOWER.FCStd',     'TOWER_タワー本体'),
    ('ADJUSTER',  '02_ADJUSTER.FCStd',  'ADJUSTER_ピッチ調整'),
    ('CAM_MOUNT', '03_CAM_MOUNT.FCStd', 'CAM_MOUNT_D455固定'),
]


def set_view(obj, rgb, transp=0, visible=True):
    if not HAS_GUI:
        return
    try:
        obj.ViewObject.ShapeColor = rgb
        obj.ViewObject.Transparency = transp
        obj.ViewObject.Visibility = visible
    except Exception:
        pass


def backup(path):
    if not os.path.exists(path):
        return None
    if not os.path.isdir(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    base = os.path.basename(path)
    dst = os.path.join(BACKUP_DIR, base.replace('.FCStd', '.%s.FCStd' % stamp))
    shutil.copy2(path, dst)
    return dst


def add_ref(newdoc, name, label, shape):
    o = newdoc.addObject('Part::Feature', name)
    o.Label = label
    o.Shape = shape
    set_view(o, COL_REF, REF_TRANSP)
    return o


def split():
    src = _master()
    if not os.path.isdir(PARTS_DIR):
        os.makedirs(PARTS_DIR)

    # 参照用に現状の形状を控えておく (Placement 適用後の実形状)
    shapes = {}
    for nm in ('Body', 'ADJUSTER', 'CAM_MOUNT'):
        shapes[nm] = src.getObject(nm).Shape.copy()
    d455 = src.getObject('D455_REF')
    shapes['D455'] = d455.Shape.copy() if d455 else None
    # 締結部品 (ボルト・ワッシャ・ナット) の参照ソリッド
    bolts = [(o.Name, o.Shape.copy(), o.Label)
             for o in src.Objects if o.Name.startswith('REF_Bolt')]
    print('  fasteners to carry over:', len(bolts))

    made = []
    for src_name, fname, label in PARTS:
        path = os.path.join(PARTS_DIR, fname)
        bak = backup(path)
        if bak:
            print('  backup ->', os.path.relpath(bak, ROOT))

        # 既に開いていたら閉じる
        for d in list(App.listDocuments().values()):
            if d.FileName and os.path.normcase(d.FileName) == os.path.normcase(path):
                App.closeDocument(d.Name)

        docname = os.path.splitext(fname)[0]
        nd = App.newDocument(docname)

        # 本体を履歴ごとコピー
        body = nd.copyObject(src.getObject(src_name), True)
        body.Label = label
        nd.recompute()
        set_view(body, COL.get(src_name, (0.7, 0.7, 0.7)))

        # 相手部品を参照ソリッドとして入れる
        for other in ('Body', 'ADJUSTER', 'CAM_MOUNT'):
            if other == src_name:
                continue
            add_ref(nd, 'REF_' + other, 'REF_%s_参照_印刷対象外' % other, shapes[other])
        if shapes['D455'] is not None and src_name != 'Body':
            add_ref(nd, 'REF_D455', 'REF_D455_参照外形_印刷対象外', shapes['D455'])
        # 締結部品 (ボルト・ワッシャ・ナット) の参照も入れる
        for bn, bshape, blabel in bolts:
            o = add_ref(nd, bn, blabel, bshape)
            set_view(o, COL_BOLT, 20)

        nd.Comment = ('jetracer_d455_mount.FCMacro.py が生成したアセンブリ '
                      'タワー.FCStd から split_parts.FCMacro.py で切り出した部品ファイル。'
                      '座標系はアセンブリと共通 (原点 = タワー底面の中心)。'
                      'REF_ で始まるものは当たり確認用の参照ソリッドで印刷対象外。')
        nd.recompute()
        nd.saveAs(path)
        made.append((path, body))

        n_sk = len([o for o in body.Group if o.TypeId == 'Sketcher::SketchObject'])
        n_fc = len([o for o in body.Group
                    if o.TypeId == 'Sketcher::SketchObject' and o.FullyConstrained])
        print('  %-22s solids=%d vol=%9.1f  sketches=%d (fully constrained %d)'
              % (fname, len(body.Shape.Solids), body.Shape.Volume, n_sk, n_fc))
    return made


def check_fit():
    """部品ファイルを個別に編集したあと、当たりだけ確認するための関数。
    3つの部品ファイルを開いて形状を読み、ピッチ ±20deg 全域で干渉を見る。"""
    import math
    sh = {}
    PIV = None

    for src_name, fname, _ in PARTS:
        path = os.path.join(PARTS_DIR, fname)
        # ドキュメント内部名は数字始まりを避けて "_01_TOWER" のようになるので
        # 名前ではなく FileName で引き当てる
        d = None
        for cand in App.listDocuments().values():
            if cand.FileName and os.path.normcase(cand.FileName) == os.path.normcase(path):
                d = cand
                break
        if d is None:
            d = App.openDocument(path)
        obj = [o for o in d.Objects
               if o.TypeId == 'PartDesign::Body' and not o.Name.startswith('REF_')][0]
        sh[src_name] = obj.Shape.copy()
        if src_name == 'ADJUSTER':
            # 回転軸はハードコードせず Sk_A5_PivotArc の円から読む
            a5 = d.getObject('Sk_A5_PivotArc')
            cir = [g for g in a5.Geometry if g.TypeId == 'Part::GeomCircle'][0]
            PIV = App.Vector(0, cir.Center.x, cir.Center.y)

    worst = 0.0
    print('pivot =', PIV)
    print('deg |  ADJ x CAM  |  TOWER x ADJ')
    tv = sh['Body'].common(sh['ADJUSTER']).Volume
    for deg in range(-20, 21, 4):
        pl = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), deg), PIV)
        sc = sh['CAM_MOUNT'].copy()
        sc.transformShape(pl.Matrix)
        v = sh['ADJUSTER'].common(sc).Volume
        worst = max(worst, v)
        print('%4d| %11.4f | %11.4f' % (deg, v, tv))
    print('worst ADJxCAM =', worst, '/ TOWERxADJ =', tv)
    return worst


if __name__ == '__main__':
    print('--- split parts ---')
    made = split()
    App.setActiveDocument(_master().Name)
    print('done. files in', PARTS_DIR)
