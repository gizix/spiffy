# app/randomizer/forms.py
from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    FieldList,
    FormField,
    SelectField,
    IntegerField,
    SubmitField,
)
from wtforms.validators import DataRequired, Optional, NumberRange


class RuleForm(FlaskForm):
    rule_type = SelectField(
        "Rule Type",
        choices=[
            ("artist_limit", "Maximum songs per artist"),
            ("min_duration", "Minimum playlist duration (minutes)"),
            # Add more rule types here as needed
        ],
    )
    parameter = StringField("Value", validators=[DataRequired()])

    class Meta:
        csrf = False  # Not needed for nested forms


class RandomizerConfigForm(FlaskForm):
    name = StringField("Configuration Name", validators=[DataRequired()])
    rules = FieldList(FormField(RuleForm), min_entries=1)
    submit = SubmitField("Save Configuration")
