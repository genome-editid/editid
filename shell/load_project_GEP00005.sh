BASEDIR=$(dirname "$0")/..
cd $BASEDIR

source venv/bin/activate

PROJNAME='GEP00005'
PROJDIR=data/${PROJNAME}

echo 'Loading project' ${PROJNAME}
python python/scripts/load_layout.py --layout=${PROJDIR}/${PROJNAME}.xlsx  --geid=${PROJNAME}
