# manage.py

from flask.ext.script import Manager

from beer import app, db, User, Beer, Rating, Glass

manager = Manager(app)

@manager.command
def initdb():
    db.create_all()

    u1 = User(email='foo@bar.com', username='foobar', password='testdata1')
    u2 = User(email='foo@baz.com', username='foobaz', password='testdata2')
    u3 = User(email='@', username='hihi', password='')

    g1 = Glass(glass_name='standard')

    b1 = Beer(created_by=u1, name='Sotted Cow', ibu=20,calories=100,abv=12,brewery='pabst', glass=g1)
    b2 = Beer(created_by=u2, name='Newcastle', ibu=30,calories=200,abv=24,brewery='new glarus', glass=g1)
    b3 = Beer(created_by=u1, name='Hebrew The Chosen Beer', ibu=40,calories=300,abv=36,brewery='miller', glass=g1)

    r1 = Rating(user=u1, beer=b1, aroma=5, appearance=5, taste=5, palate=5, bottle=4)
    r2 = Rating(user=u2, beer=b2, aroma=4, appearance=4, taste=4, palate=4, bottle=5)
    
    db.session.add(u1)
    db.session.add(u2)
    db.session.add(u3)

    db.session.add(g1)

    db.session.add(b1)
    db.session.add(b2)
    db.session.add(b3)

    db.session.add(r1)
    db.session.add(r2)

    db.session.commit()

@manager.command
def dropdb():
    db.drop_all()

if __name__ == '__main__':
    manager.run()
