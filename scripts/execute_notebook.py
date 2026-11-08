"""Execute a trusted repository analysis notebook with a private local IPC kernel."""
import argparse
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[1]


def execute(source,destination):
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import KernelManager
    source=Path(source).resolve();destination=Path(destination)
    if (ROOT/'notebooks').resolve() not in source.parents or source.suffix!='.ipynb':raise ValueError('Select a repository analysis notebook')
    (ROOT/'.cache').mkdir(exist_ok=True);destination.parent.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'));os.environ.setdefault('IPYTHONDIR',str(ROOT/'.cache/ipython'))
    notebook=nbformat.read(source,as_version=4)
    with TemporaryDirectory(prefix='analysis-ipc-',dir=ROOT/'.cache') as directory:
        km=KernelManager(kernel_name='python3',transport='ipc',ip=str(Path(directory)/'k'))
        km.kernel_spec.argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}']
        try:NotebookClient(notebook,km=km,timeout=600,resources={'metadata':{'path':str(ROOT)}}).execute()
        finally:
            if km.has_kernel:km.shutdown_kernel(now=True)
            km.cleanup_resources()
    nbformat.write(notebook,destination)
    print('Executed',len(notebook.cells),'analysis cells; output saved privately. No inference performed.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();execute(args.source,args.out)
