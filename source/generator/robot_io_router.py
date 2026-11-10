"""I/O-only maze geometry:0.23mm guard,0.20mm beside fine-pitch small vias.

The latter is the actual native rule, needed beside0.5mm-pitch fanouts. Native
DRC remains authoritative; this sampler is only a candidate-route tool.
"""
import pcbnew as p
from indexed_fixer import IndexedFixer
from fixer import T,MM

class RobotIOFixer(IndexedFixer):
    def free(self,layer,net,x,y,half):
        if not(T(self.edge.GetLeft())+half+.5<x<T(self.edge.GetRight())-half-.5 and
               T(self.edge.GetTop())+half+.5<y<T(self.edge.GetBottom())-half-.5):return False
        pt=p.VECTOR2I(MM(x),MM(y))
        for item in self._items(layer,net,x,y,half+2.3):
            small_via=item.GetClass()=='PCB_VIA' and T(item.GetWidth())<=.40001
            clearance=.20 if small_via or abs(half-.2)<.00001 else .23
            if item.HitTest(pt,MM(half+clearance)):return False
        if layer in (p.F_Cu,p.B_Cu):
            for z in self.b.Zones():
                if z.GetLayer()==layer and z.GetNetname() not in(net,'GND') and z.Outline().Collide(pt,MM(half+.23)):return False
        return True
