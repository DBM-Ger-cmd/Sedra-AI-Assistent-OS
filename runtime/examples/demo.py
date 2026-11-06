from pathlib import Path
from sedra_runtime.runtime import SedraRuntime

root=Path(__file__).resolve().parents[1]
arch=sorted((root.parent/'architecture').glob('SEDRA_Architecture_v*'))[-1]
rt=SedraRuntime(root,arch)
print(rt.boot())
m=rt.brain.create_mission('Create a demo artifact')
print(rt.brain.run(m['identity']['mission_id']))
