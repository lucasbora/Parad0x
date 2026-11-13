import sys
sys.path.insert(0, ".")
from app.corridor.inputs import write_reference_files
from app.corridor.osm_network import load_network
for p in write_reference_files(load_network()):
    print(p.name)
