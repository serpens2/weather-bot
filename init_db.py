from utils import with_db, db_exists
import logging

log = logging.getLogger(__name__)

@with_db
def init_db(cur):
    if not db_exists("weatherbot"):
        query = """
        CREATE TABLE weatherbot (
            chat_id VARCHAR(20) NOT NULL PRIMARY KEY,
            lat FLOAT NOT NULL,
            lon FLOAT NOT NULL,
            tz_offset SMALLINT NOT NULL,
            notify VARCHAR(5)
        );
        """
        cur.execute(query)
        log.info("Database created")

if __name__ == "__main__":
    init_db()