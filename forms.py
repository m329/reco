from flask.ext.wtf import Form
from wtforms import StringField
from wtforms.validators import DataRequired

class FavoritesForm(Form):
	a1 = StringField('a1', validators=[DataRequired()])
	a2 = StringField('a2', validators=[DataRequired()])
	a3 = StringField('a3', validators=[DataRequired()])

