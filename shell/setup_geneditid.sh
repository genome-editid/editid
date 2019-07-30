BASEDIR=$(dirname "$0")/..
cd $BASEDIR

echo 'Creating Python3 virtual environment'
python3 -m venv venv
source venv/bin/activate

echo 'Installing GenEditID dependencies'
pip install -e python/.

echo 'Copying GenEditID configuraton file'
cp python/dnascissors/geneditid.yml.sample python/dnascissors/geneditid.yml

echo 'Creating the GenEditID database'
python python/scripts/create_db.py

echo 'Loading GenEditID reference data'
python python/scripts/load_ref_data.py

echo 'Installing Homo Sapiens reference genome'
pyensembl install --release 95 --species homo_sapiens

echo 'Create symlink to template file for accessing it from the WebApp'
ln -s data/templates/GEPXXXXX.xlsx python/webapp/static
