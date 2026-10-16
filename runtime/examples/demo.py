from pathlib import Path
from guppi_runtime.runtime import GuppiRuntime

root=Path(__file__).resolve().parents[1]
arch=sorted((root.parent/'architecture').glob('GUPPI_Architecture_v*'))[-1]
rt=GuppiRuntime(root,arch)
print(rt.boot())
m=rt.brain.create_mission('Create a demo artifact')
print(rt.brain.run(m['identity']['mission_id']))
