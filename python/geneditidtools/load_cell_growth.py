import sqlalchemy

import geneditid.log as logger
from geneditid.config import cfg
from geneditid.model import Base
from geneditid.loader import CellGrowthLoader


def main():
    import argparse
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--plateid", dest="plateid", action="store", help="The plate ID e.g. 'GEP00001_01'", required=True)
    parser.add_argument("--file", dest="file", action="store", help="The Incucyte file e.g. 'GEP00001_01 data/20170127_GEP00001/GEP00001_01_incu.txt'.", required=True)
    parser.add_argument("--clean", dest="clean", action="store_true", default=False, help="Clean database before loading?")
    options = parser.parse_args()

    log = logger.get_custom_logger(os.path.join(cfg['PROJECTS_FOLDER'], 'load_cell_growth.log'))

    engine = sqlalchemy.create_engine(cfg['DATABASE_URI'])
    Base.metadata.bind = engine
    DBSession = sqlalchemy.orm.sessionmaker(bind=engine)
    session = DBSession()
    loader = CellGrowthLoader(session, options.file, options.plateid)

    try:
        if options.clean:
            loader.clean()
        loader.load()
        session.commit()
    except Exception as e:
        log.exception(e)
        session.rollback()
    finally:
        session.close()


if __name__ == '__main__':
    main()
