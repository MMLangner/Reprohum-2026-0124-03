 
from flask.cli import FlaskGroup

from project import app, db
from project import initTasks

cli = FlaskGroup(app)

@cli.command("create_db")
def create_db():
    db.drop_all()
    db.create_all()
    db.session.commit()



@cli.command("initTasks")
def seed_tasks():
    initTasks(db)

if __name__ == "__main__":
    cli()