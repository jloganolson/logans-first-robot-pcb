"""Spatial lookup for the existing maze router; geometry is still checked by KiCad.
This only reduces the candidate set, never relaxes the clearance rules.
"""
import math
import pcbnew
from fixer import Fixer, ALL, T
class IndexedFixer(Fixer):
    def __init__(self, board):
        super().__init__(board)
        self._index = None
    def _items(self, layer, net, x, y, r):
        if self._index is None:
            self._index={}
            self._objects=list(self.b.GetTracks())+[p for f in self.b.GetFootprints() for p in f.Pads()]
            for i,it in enumerate(self._objects):
                bb=it.GetBoundingBox()
                for L in ALL:
                    if isinstance(it,pcbnew.PAD): on=it.IsOnLayer(L)
                    else:on=it.GetClass()=='PCB_VIA' or it.GetLayer()==L
                    if not on:continue
                    for ix in range(math.floor(T(bb.GetLeft())/2),math.floor(T(bb.GetRight())/2)+1):
                        for iy in range(math.floor(T(bb.GetTop())/2),math.floor(T(bb.GetBottom())/2)+1):
                            self._index.setdefault((L,ix,iy),[]).append(i)
        ids=set()
        for ix in range(math.floor((x-r)/2),math.floor((x+r)/2)+1):
            for iy in range(math.floor((y-r)/2),math.floor((y+r)/2)+1):ids.update(self._index.get((layer,ix,iy),()))
        return [self._objects[i] for i in ids if self._objects[i].GetNetname()!=net or not net]
    def add_track(self,*args,**kwargs):
        super().add_track(*args,**kwargs);self._index=None
    def add_via(self,*args,**kwargs):
        super().add_via(*args,**kwargs);self._index=None
