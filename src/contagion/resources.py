"""Read-only host telemetry and conservative worker pause policy."""
import json
from pathlib import Path
import shutil
import subprocess

from .events import utc


def sample(previous_cpu=None):
    result={'timestamp_utc':utc(),'cpu_percent':None,'available_ram_gib':None,'temperatures_c':[],'gpu':[]}
    cpu=None
    stat=Path('/proc/stat')
    if stat.exists():
        values=[int(v) for v in stat.read_text().splitlines()[0].split()[1:]]
        cpu=(sum(values),values[3]+(values[4] if len(values)>4 else 0))
        if previous_cpu and cpu[0]>previous_cpu[0]:
            result['cpu_percent']=100*(1-(cpu[1]-previous_cpu[1])/(cpu[0]-previous_cpu[0]))
    memory=Path('/proc/meminfo')
    if memory.exists():
        fields={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in memory.read_text().splitlines()}
        result['available_ram_gib']=int(fields['MemAvailable'].split()[0])/2**20
    for path in Path('/sys/class/hwmon').glob('hwmon*/temp*_input'):
        try:
            value=float(path.read_text())/1000
            if 0<value<150:result['temperatures_c'].append(value)
        except (OSError,ValueError):pass
    binary=shutil.which('nvidia-smi')
    if binary:
        try:
            query=subprocess.run([binary,'--query-gpu=temperature.gpu,utilization.gpu,memory.total,memory.used,power.draw',
                '--format=csv,noheader,nounits'],check=False,capture_output=True,text=True,timeout=5)
            if query.returncode==0:
                for line in query.stdout.splitlines():
                    values=[float(v.strip()) if v.strip().replace('.','',1).isdigit() else None for v in line.split(',')]
                    if len(values)==5:result['gpu'].append(dict(zip(['temperature_c','utilization_percent','memory_total_mib','memory_used_mib','power_watts'],values)))
        except (OSError,subprocess.TimeoutExpired):pass
    return result,cpu


def pause_reason(data,max_gpu_c=85,max_sensor_c=90,min_ram_gib=4):
    if data['available_ram_gib'] is not None and data['available_ram_gib']<min_ram_gib:return 'low_available_ram'
    if any(g['temperature_c'] is not None and g['temperature_c']>=max_gpu_c for g in data['gpu']):return 'gpu_temperature_pause'
    if any(t>=max_sensor_c for t in data['temperatures_c']):return 'temperature_sensor_pause'
    return None


def record(root,data):
    root=Path(root)
    with (root/'resources.jsonl').open('a') as stream:stream.write(json.dumps(data)+'\n')
    target=root/'resources.latest.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(data));temp.replace(target)
