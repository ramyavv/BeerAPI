import re
import datetime

from flask import Flask, request, jsonify, abort
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func
from sqlalchemy.ext.hybrid import hybrid_property

app = Flask(__name__)
app.config['DEBUG'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://Penguin:@localhost:5432/beer'
#app.config['SQLALCHEMY_ECHO'] = True

db = SQLAlchemy(app)

favorites = db.Table('Favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('Users.id', ondelete='CASCADE')),
    db.Column('beer_id', db.Integer, db.ForeignKey('Beers.id', ondelete='CASCADE'))
)

def slugify(text):
    return re.sub('[^A-Za-z0-9]+', '-', text)

#User Model
class User(db.Model):
    __tablename__ = 'Users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255))
    username = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    favorite_beers = db.relationship('Beer', secondary=favorites, lazy='dynamic')

    def to_dict(self, include_rating=False):
        d = {
            'email': self.email,
            'username': self.username,
            'password': self.password,
        }

        if include_rating:
            d['ratings'] = [r.to_dict(include_beer=True) for r in self.ratings.all()]        #add rating to the user field if rating is true. diff between this and beer
        return d

 
#Glass model        
class Glass(db.Model):
    __tablename__ = 'Glasses'

    id = db.Column(db.Integer, primary_key= True)
    _name = db.Column(db.String(255), unique=True)
    slug = db.Column(db.String(255), unique=True)

    @property
    def glass_name(self):
        return self._name

    @glass_name.setter
    def glass_name(self, value):
        self._name = value
        self.slug = slugify(value)

    def to_dict(self, include_rating=True):
        d = {
        'glass_name' : self.glass_name,
        'slug': self.slug
        }
        return d


#Beer Model 
class Beer(db.Model):
    __tablename__ = 'Beers'

    id = db.Column(db.Integer, primary_key=True)
    _name = db.Column(db.String(255), unique=True)
    slug = db.Column(db.String(255), unique=True)
    ibu = db.Column(db.Integer)
    calories = db.Column(db.Integer)
    abv = db.Column(db.Float(2), db.CheckConstraint('abv >= 0'), db.CheckConstraint('abv <= 100'))
    brewery = db.Column(db.String(255))
    #foreign keys and relationships
    glass_id = db.Column(db.Integer, db.ForeignKey('Glasses.id'))
    glass = db.relationship('Glass', foreign_keys=[glass_id], backref=db.backref('beers', lazy='dynamic', viewonly=True))

    created_at = db.Column(db.DateTime, default=db.func.now())
    created_by_id = db.Column(db.Integer, db.ForeignKey('Users.id', ondelete='SET NULL'))
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self.slug = slugify(value)

    @hybrid_property
    def average_rating(self):
        count = self.ratings.count()
        if count:
            return sum([r.average for r in self.ratings]) / count
        return 0

    @average_rating.expression
    def average_rating(cls):
        return select([func.avg(Rating.average)]).where(Rating.beer_id == cls.id).label('average_rating')

    def to_dict(self, include_rating=True):
        d = {
        'name': self.name,
        'slug': self.slug,
        'ibu' : self.ibu,
        'calories' : self.calories,
        'abv' : self.abv,
        'brewery' : self.brewery,
        'glass_name': self.glass.glass_name,
        'average_rating': self.average_rating
        }
        return d

#Ratings Model


class Rating(db.Model):
    __tablename__ = 'Ratings'

    id = db.Column(db.Integer, primary_key = True)
    aroma = db.Column(db.Integer, db.CheckConstraint('aroma >= 1'), db.CheckConstraint('aroma <= 5'))
    appearance = db.Column(db.Integer, db.CheckConstraint('appearance >= 1'), db.CheckConstraint('appearance <= 5'))
    taste = db.Column(db.Integer, db.CheckConstraint('taste >= 1'), db.CheckConstraint('taste <= 5'))
    palate = db.Column(db.Integer, db.CheckConstraint('palate >= 1'), db.CheckConstraint('palate <= 5'))
    bottle = db.Column(db.Integer, db.CheckConstraint('bottle >= 1'), db.CheckConstraint('bottle <= 5'))

    created_at = db.Column(db.DateTime, default=db.func.now())

    #beerId, userId foreign keys

    user_id = db.Column(db.Integer, db.ForeignKey('Users.id'))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('ratings', lazy='dynamic', viewonly=True, cascade='all, delete'))
    beer_id = db.Column(db.Integer, db.ForeignKey('Beers.id'))
    beer = db.relationship('Beer', foreign_keys=[beer_id], backref=db.backref('ratings', lazy='dynamic', viewonly=True, cascade='all, delete'))

    @hybrid_property                      
    def average(self):
        return (self.aroma + self.appearance + self.taste + self.palate + self.bottle) / 5

    @average.expression
    def average(cls):
        return (cls.aroma + cls.appearance + cls.taste + cls.palate + cls.bottle) / 5

    def to_dict(self, include_beer=False, include_user=False):
        d = {
        'aroma' : self.aroma,
        'appearance' : self.appearance,
        'taste'      : self.taste,
        'palate'     : self.palate,
        'bottle'     : self.bottle,
        'average'    : self.average
        }

        if include_beer:
            d['beer'] = self.beer.name
        if include_user:
            d['user'] = self.user.username
        return d

#-------------------------------------------------------------Models end here---------------------------------------------#
# users views

@app.route('/users')
def list_users():
    
    user_sort_fields = {
        'username': User.username,
        '-username': User.username.desc(),
        'email': User.email,
        '-email': User.email.desc()
    }

    try:
        sort_param = request.args.get('sort', None)
        sort_field = user_sort_fields.get(sort_param)
    except KeyError:
        sort_field = user_sort_fields['username']

    users = User.query
    users = users.order_by(sort_field)
    users = users.all()

    return jsonify({'users': [u.to_dict() for u in users]})   

@app.route('/users/<string:username>')
def get_user(username):
    """Retrieves a particular user by username."""
    try:
        user = User.query.filter_by(username=username).one()  
        return jsonify(user.to_dict())
    except NoResultFound:
        abort(404)

#add user details
@app.route('/users', methods=['POST'])
def create_user():
    """Creates a new user. Requires email, username, and password in input json."""
    data = request.get_json(force=True)

    
    user = User()
    db.session.add(user)

    try:
        user.email = str(data['email'])

        if '@' not in user.email or user.email == '':
            return jsonify({'error': 'email looks invalid'})
    except KeyError, ValueError:
        return jsonify({'error': 'bad or missing email'})

    try:
        user.username = str(data['username'])

        if user.username == '':
            return jsonify({'error': 'username cannot be empty'})
        if slugify(user.username) != user.username:
            return jsonify({'error': 'username contained invalid characters'})
    except KeyError, ValueError:
        return jsonify({'error': 'bad or missing username'})

    try:
        user.password = str(data['password'])
        if user.password == '':
            return jsonify({'error': 'password is empty'})
    except KeyError, ValueError:
        return jsonify({'error': 'bad or missing password'})

    try:
        db.session.commit()
    except IntegrityError:
        return '', 409
    
    return '', 201

#edit user details 
@app.route('/users/<string:username>', methods=['PUT'])
def edit_user(username):
    try:
        user = User.query.filter_by(username=username).one()
    except NoResultFound:
        abort(404)
    
    data = request.get_json(force=True)

    try:
        user.email = str(data['email'])

        if '@' not in user.email or user.email == '':
            return jsonify({'error': 'email looks invalid'})
    except ValueError:
        return jsonify({'error': 'bad or missing email'})
    except KeyError:
        pass

    try:
        user.username = str(data['username'])

        if user.username == '':
            return jsonify({'error': 'username is empty'})
        if slugify(user.username) != user.username:
            return jsonify({'error': 'username contained invalid characters'})
    except ValueError:
        return jsonify({'error': 'bad username'})
    except KeyError:
        pass

    try:
        user.password = str(data['password'])
    except ValueError:
        return jsonify({'error': 'bad password'})
    except KeyError:
        pass

    db.session.commit()
    return jsonify(user.to_dict())


#delete user
@app.route('/users/<string:username>', methods=['DELETE'])
def delete_user(username):
    try:
        user = User.query.filter_by(username=username).one()
    except NoResultFound:
        abort(404)
    db.session.delete(user)
    db.session.commit()
    return '',204


@app.route('/beers')
def list_beers():
    """Returns a list of beers."""
    

    beer_sort_fields = {
        'name': Beer._name,
        '-name': Beer._name.desc(),
        'calories': Beer.calories,
        '-calories': Beer.calories.desc(),
        'abv': Beer.abv,
        '-abv': Beer.abv.desc(),
        'brewery':Beer.brewery,
        '-brewery': Beer.brewery.desc(),
        'ibu' : Beer.ibu,
        '-ibu' : Beer.ibu.desc()
    }

    try:
        sort_param = request.args.get('sort', None)
        sort_field = beer_sort_fields.get(sort_param)
    except KeyError:
        sort_field = beer_sort_fields['name']

    beers = Beer.query 
    beers = beers.order_by(sort_field)
    beers = beers.all()

    return jsonify({'beers': [b.to_dict() for b in beers]})

#get by name
@app.route('/beers/<string:name>')
def get_beer(name):
    """Returns a particular beer by name."""
    try:
        beer = Beer.query.filter_by(slug=name).one()  
        return jsonify(beer.to_dict())
    except NoResultFound:
        abort(404)

#add a beer
@app.route('/beers', methods=['POST'])
def create_beer():
    """Creates a new beer. Requires ibu, calories, abv, brewery, and glass type in input json."""
    data = request.get_json(force=True)

   
    beer = Beer()        
    db.session.add(beer)


    latest = Beer.query
    latest = latest.join(Beer.created_by)
    latest = latest.filter(User.username == data['username'])
    latest = latest.order_by(Beer.created_at.desc())
    latest = latest.first()

    if latest is not None and latest.created_at > datetime.datetime.now() - datetime.timedelta(days=1):
        return jsonify({'error': 'User already created beer today', 'beer': latest.to_dict()}), 422

    try:
        glass = Glass.query.filter_by(slug=data['glass_name']).one()
        beer.glass = glass
        if(glass.glass_name == ''):
            return jsonify({'error': 'glass name cannot be empty'})
    except (KeyError, NoResultFound) as e:
        return jsonify({'error': 'glass name not found or missing values'}), 422

    try:
        beer.name = str(data['name'])
        if(beer.name == ''):
            return jsonify({'error': 'beername cannot be empty'})
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format in name or missing values'})

    try:
        beer.ibu = int(data['ibu'])
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format in ibu or missing values'})

    try:
        beer.calories = int(data['calories'])
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format calories or missing values'})

    try:
        beer.abv = int(data['abv'])
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format abv or missing values'})

    try:
        beer.brewery = str(data['brewery'])
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format brewery or missing values'})

    try:
        db.session.commit()
    except IntegrityError:
        return '', 409
    
    return '', 201
    
    

    


@app.route('/beers/<string:name>', methods=['PUT'])
def edit_beer(name):
    data = request.get_json(force=True)
    
    try:
        beer = Beer.query.filter_by(slug=name).one()  
    except NoResultFound:
        abort(404)
    
    try:
        glass = Glass.query.filter_by(slug=data['glass_name']).one()
        beer.glass = glass
    except NoResultFound:
        return jsonify({'error': 'glass name not found'}), 422
    except KeyError:
        pass

    try:
        beer.name = str(data['name'])
        if(beer.name == ''):
            return jsonify({'error': 'beer name cannot be empty'})
    except ValueError:
        return jsonify({'error': 'bad format in name or missing values'})
    except KeyError:
        pass

    try:
        beer.ibu = int(data['ibu'])
    except ValueError:
        return jsonify({'error': 'bad format in ibu'})
    except KeyError:
        pass

    try:
        beer.calories = int(data['calories'])
    except ValueError:
        return jsonify({'error': 'bad format calories'})
    except KeyError:
        pass

    try:
        beer.abv = int(data['abv'])
    except ValueError:
        return jsonify({'error': 'bad format abv'})
    except KeyError:
        pass

    try:
        beer.brewery = str(data['brewery'])
    except ValueError:
        return jsonify({'error': 'bad format brewery'})
    except KeyError:
        pass

    db.session.commit()
    return jsonify(beer.to_dict())

#delete a beer from list of beers
@app.route('/beers/<string:beer>', methods=['DELETE'])
def delete_beer(beer):
    try:
        beer = Beer.query.filter_by(slug=beer).one()
    except NoResultFound:
        abort(404)

    db.session.delete(beer)
    db.session.commit()
    return '',204

#
# /glasses views
#
#get all glass
@app.route('/glasses')
def list_glasses():
    """Retrieves a list of glass names."""
    return jsonify({'glasses': [g.to_dict() for g in Glass.query.all()]})

  

#add a glass
@app.route('/glasses', methods=['POST'])
def create_glass():
    """Creates a new glass type. Requires name in input json."""
    data = request.get_json(force=True)

    glass = Glass()
    db.session.add(glass)

    try:
        glass.glass_name = str(data['glass_name'])
        if(glass.glass_name == ''):
            return jsonify({ 'error': 'glass name cannot be empty'})
    except KeyError, ValueError:
        return jsonify({'error': 'bad format in glass_name or missing values'})

    db.session.commit()
    return '', 201


# update glass
@app.route('/glasses/<string:glass_name>', methods=['PUT'])
def edit_glass(glass_name):
    try:
        glass = Glass.query.filter_by(slug=glass_name).one()
    except NoResultFound:
        abort(404)

    data = request.get_json(force=True)

    try:
        glass.glass_name = str(data['glass_name'])
        if(glass.glass_name == ''):
            return jsonify({ 'error': 'glass name cannot be empty'})
    except ValueError:
        return jsonify({'error': 'bad format in glass_name or missing values'})
    except KeyError:
        pass

    db.session.commit()
    return jsonify(glass.to_dict())


#delete a particular glass
@app.route('/glasses/<string:glass_name>', methods=['DELETE'])
def delete_glass(glass_name):
    try:
        glass = Glass.query.filter_by(slug=glass_name).one()
    except NoResultFound:
        abort(404)

    db.session.delete(glass)

    try:
        db.session.commit()
    except IntegrityError:
        return jsonify({'error': 'Glass is referenced by a beer. Please empty glass first ;)'}), 422

    return '', 204


# /ratings views 
#
@app.route('/ratings')
def get_ratings():
    ratings_sort_fields = {
        'aroma': Rating.aroma,
        '-aroma': Rating.aroma.desc(),
        'appearance': Rating.appearance,
        '-appearance': Rating.appearance.desc(),
        'taste': Rating.taste,
        '-taste': Rating.taste.desc(),
        'palate':Rating.palate,
        '-palate': Rating.palate.desc(),
        'bottle' : Rating.bottle,
        '-bottle': Rating.bottle.desc(),
        'average': Rating.average,
        '-average': Rating.average.desc()
    }

    try:
        sort_param = request.args.get('sort', None)
        sort_field = ratings_sort_fields.get(sort_param)
    except KeyError:
        sort_field = ratings_sort_fields['average']

    ratings = Rating.query 
    ratings = ratings.order_by(sort_field)
    ratings = ratings.all()

    return jsonify({'ratings': [r.to_dict(include_beer=True, include_user=True) for r in ratings]})

@app.route('/users/<string:username>/ratings')
def get_user_ratings(username):
    """Returns a list of ratings created by a particular user (by username)."""
    
    try:
        user = User.query.filter_by(username=username).one()
    except NoResultFound:
        abort(404)

    # SORT 
    ratings_sort_fields = {
        'aroma': Rating.aroma,
        '-aroma': Rating.aroma.desc(),
        'appearance': Rating.appearance,
        '-appearance': Rating.appearance.desc(),
        'taste': Rating.taste,
        '-taste': Rating.taste.desc(),
        'palate':Rating.palate,
        '-palate': Rating.palate.desc(),
        'bottle' : Rating.bottle,
        '-bottle': Rating.bottle.desc(),
        'average': Rating.average,
        '-average': Rating.average.desc()
    }

    try:
        sort_param = request.args.get('sort', None)
        sort_field = ratings_sort_fields.get(sort_param)
    except KeyError:
        sort_field = ratings_sort_fields['average']

    ratings = user.ratings
    ratings = ratings.order_by(sort_field)
    ratings = ratings.all()
    
    return jsonify({'ratings': [r.to_dict(include_beer=True) for r in ratings]})  

@app.route('/users/<string:username>/ratings/<string:beer>')
def get_user_rating_for_beer(username, beer):
    """Returns a rating created by a particular usre (by username) about a particular beer (by name)."""
    try:
        query = Rating.query
        query = query.join(Rating.user)
        query = query.join(Rating.beer)
        query = query.filter(User.username == username, Beer.slug == beer)

        rating = query.one()
        return jsonify({'rating': rating.to_dict(include_beer=True, include_user=True)})  
    except NoResultFound:
        abort(404)


@app.route('/users/<string:username>/ratings/<string:beer>', methods=['PUT'])
def update_user_rating_for_beer(username, beer):
    """Creates a rating created by a particular user (by username) about a particular beer (by name)."""
    try:
        query = Rating.query
        query = query.join(Rating.user)
        query = query.join(Rating.beer)
        query = query.filter(User.username == username, Beer.slug == beer)

        rating = query.one()
    except NoResultFound:
        abort(404)

    data = request.get_json(force=True)  

    try:
        rating.aroma = int(data['aroma'])
        if rating.aroma < 1 or rating.aroma > 5:
            raise ValueError()
    except ValueError:
        return jsonify({'error': 'bad format of aroma or missing values'})
    except KeyError:
        pass

    try:
        rating.appearance = int(data['appearance'])
        if rating.appearance < 1 or rating.appearance > 5:
            raise ValueError()
        rating.appearance = int(data['appearance'])
    except ValueError:
        return jsonify({'error': 'bad format of appearance or missing values'})
    except KeyError:
        pass

    try:
        rating.taste = int(data['taste'])
        if rating.taste < 1 or rating.taste > 5:
            raise ValueError()
        rating.taste = int(data['taste'])
    except ValueError:
        return jsonify({'error': 'bad format of taste or missing values'})
    except KeyError:
        pass

    try:
        rating.palate = int(data['palate'])
        if rating.palate < 1 or rating.palate > 5:
            raise ValueError()
        rating.palate = int(data['palate'])
    except ValueError:
        return jsonify({'error': 'bad format of palate or missing values'})
    except KeyError:
        pass

    try:
        rating.bottle = int(data['bottle'])
        if rating.bottle < 1 or rating.bottle > 5:
            raise ValueError()
        rating.bottle = int(data['bottle'])
    except ValueError:
        return jsonify({'error': 'bad format of bottle or missing values'})
    except KeyError:
        pass

    return jsonify({'rating': rating.to_dict(include_beer=True, include_user=True)})  

@app.route('/users/<string:username>/ratings/<string:beer>', methods=['DELETE'])
def delete_user_rating_for_beer(username, beer):
    """deletes a rating created by a particular usre (by username) about a particular beer (by name)."""
    try:
        query = Rating.query
        query = query.join(Rating.user)
        query = query.join(Rating.beer)
        query = query.filter(User.username == username, Beer.slug == beer)

        rating = query.one()
        return jsonify({'rating': rating.to_dict(include_beer=True, include_user=True)})  
    except NoResultFound:
        abort(404)

    db.session.remove(rating)
    db.session.commit()
    return '', 204

#get ratings of a particular beer
@app.route('/beers/<string:name>/ratings')
def get_beer_ratings(name):
    """Returns a list of ratings about a particular beer (by name)."""
    try:
        beer = Beer.query.filter_by(slug=name).one()
    except NoResultFound:
        abort(404)

    ratings_sort_fields = {
        'aroma': Rating.aroma,
        '-aroma': Rating.aroma.desc(),
        'appearance': Rating.appearance,
        '-appearance': Rating.appearance.desc(),
        'taste': Rating.taste,
        '-taste': Rating.taste.desc(),
        'palate':Rating.palate,
        '-palate': Rating.palate.desc(),
        'bottle' : Rating.bottle,
        '-bottle': Rating.bottle.desc(),
        'average': Rating.average,
        '-average': Rating.average.desc()
    }

    try:
        sort_param = request.args.get('sort', None)
        sort_field = ratings_sort_fields.get(sort_param)
    except KeyError:
        sort_field = ratings_sort_fields['average']

    ratings = Beer.ratings
    ratings = ratings.order_by(sort_field)
    ratings = ratings.all()
    
    return jsonify({'ratings': [r.to_dict(include_user=True) for r in beer.ratings]})
        
#add a rating
@app.route('/ratings', methods=['POST'])
def create_rating():
    """Creates a new rating. Requires aroma, appearance, taste, palate, bottle, beer, and user in input json."""
    data = request.get_json(force=True)  
    rating = Rating()
    db.session.add(rating)

    try:
        beer = Beer.query.filter_by(slug=data['beer']).one()

    except (KeyError, NoResultFound) as e:
        return jsonify({'error': 'beer not found or missing values'}), 422

    try:
        user = User.query.filter_by(username=data['username']).one()
        beer.created_by = user
    except (KeyError, NoResultFound) as e:
        return jsonify({'error': 'user not found or missing values'}), 422

    latest = Rating.query
    latest = latest.join(Rating.user)
    latest = latest.filter(User.username == data['username'])
    latest = latest.order_by(Rating.created_at.desc())
    latest = latest.first()

    if latest is not None and latest.created_at > datetime.datetime.now() - datetime.timedelta(days=7):
        return jsonify({'error': 'User already created a rating this week', 'rating': latest.to_dict()}), 422
    
    query = Rating.query
    query = query.join(Rating.user)
    query = query.join(Rating.beer)
    query = query.filter(User.username == data['username'], Beer.slug == data['beer'])

    if query.count():
        return jsonify({'error': 'User already reviewed this beer', 'rating': latest.to_dict()}), 422

    rating.beer = beer
    rating.user = user

    try:
        rating.aroma = int(data['aroma'])
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format of aroma or missing values'})

    try:
        rating.appearance = int(data['appearance'])
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format of appearance or missing values'})

    try:
        rating.taste = int(data['taste'])
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format of taste or missing values'})

    try:
        rating.palate = int(data['palate'])
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format of palate or missing values'})

    try:
        rating.bottle = int(data['bottle'])
    except (KeyError, ValueError) as e:
        return jsonify({'error': 'bad format of bottle or missing values'})

    db.session.commit()
    return '', 201

    
    
  
   
#---------------------------------------------------------------
#favorites

#favorites of a particular user
@app.route('/users/<string:username>/favorites')
def get_favorites(username):
    try:
        user = User.query.filter_by(username=username).one() 

        return jsonify({'beers':[b.to_dict() for b in user.favorite_beers.all()]})
    except NoResultFound:
        abort(404)

#add particular beer to a user's favorite list
@app.route('/users/<string:username>/favorites/<string:beer>', methods=['PUT'])
def create_favorites(username, beer):
    try:
        user = User.query.filter_by(username=username).one()
        beer=Beer.query.filter_by(slug=beer).one() 
    except NoResultFound:
        abort(404)

    user.favorite_beers.append(beer)
    db.session.commit()
    return '', 201

#delete beer from a user's favorite list
@app.route('/users/<string:username>/favorites/<string:beer>', methods=['DELETE'])
def delete_favorties(username, beer):
    try:
        user = User.query.filter_by(username=username).one()
        beer=Beer.query.filter_by(slug=beer).one() 
    except NoResultFound:
        abort(404)

    user.favorite_beers.remove(beer)
    db.session.commit()
    return '', 204







    