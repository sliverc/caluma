import sys
from logging import getLogger

from django_filters.constants import EMPTY_VALUES
from rest_framework import exceptions

from caluma.data_source.data_source_handlers import (
    get_data_source_data,
    get_data_sources,
)

from . import jexl
from .format_validators import get_format_validators
from .models import Answer, Question

log = getLogger()


class CustomValidationError(exceptions.ValidationError):
    """Custom validation error to carry more information.

    This can carry more information about the error, so the documentValidity
    query can show more useful information.
    """

    def __init__(self, detail, code=None, slugs=[]):
        super().__init__(detail, code)
        self.slugs = slugs


class AnswerValidator:
    def __init__(self, do_check_required=True):
        self.do_check_required = do_check_required

    def _validate_question_text(self, question, value, **kwargs):
        max_length = (
            question.max_length if question.max_length is not None else sys.maxsize
        )
        if not isinstance(value, str) or len(value) > max_length:
            raise CustomValidationError(
                f"Invalid value {value}. "
                f"Should be of type str and max length {max_length}",
                slugs=[question.slug],
            )

    def _validate_question_textarea(self, question, value, **kwargs):
        self._validate_question_text(question, value)

    def _validate_question_float(self, question, value, **kwargs):
        min_value = (
            question.min_value if question.min_value is not None else float("-inf")
        )
        max_value = (
            question.max_value if question.max_value is not None else float("inf")
        )

        if not isinstance(value, float) or value < min_value or value > max_value:
            raise CustomValidationError(
                f"Invalid value {value}. "
                f"Should be of type float, not lower than {min_value} "
                f"and not greater than {max_value}",
                slugs=[question.slug],
            )

    def _validate_question_integer(self, question, value, **kwargs):
        min_value = (
            question.min_value if question.min_value is not None else float("-inf")
        )
        max_value = (
            question.max_value if question.max_value is not None else float("inf")
        )

        if not isinstance(value, int) or value < min_value or value > max_value:
            raise CustomValidationError(
                f"Invalid value {value}. "
                f"Should be of type int, not lower than {min_value} "
                f"and not greater than {max_value}",
                slugs=[question.slug],
            )

    def _validate_question_date(self, question, value, **kwargs):
        pass

    def _validate_question_choice(self, question, value, **kwargs):
        options = question.options.values_list("slug", flat=True)
        if not isinstance(value, str) or value not in options:
            raise CustomValidationError(
                f"Invalid value {value}. "
                f"Should be of type str and one of the options {'.'.join(options)}",
                slugs=[question.slug],
            )

    def _validate_question_multiple_choice(self, question, value, **kwargs):
        options = question.options.values_list("slug", flat=True)
        invalid_options = set(value) - set(options)
        if not isinstance(value, list) or invalid_options:
            raise CustomValidationError(
                f"Invalid options [{', '.join(invalid_options)}]. "
                f"Should be one of the options [{', '.join(options)}]",
                slugs=[question.slug],
            )

    def _validate_question_dynamic_choice(self, question, value, info, **kwargs):
        data_source = get_data_sources(dic=True)[question.data_source]
        if not data_source.validate:
            if not isinstance(value, str):
                raise CustomValidationError(
                    f'Invalid value: "{value}". Must be of type str',
                    slugs=[question.slug],
                )
            return

        data = get_data_source_data(info, question.data_source)
        options = [d.slug for d in data]

        if not isinstance(value, str) or value not in options:
            raise CustomValidationError(
                f'Invalid value "{value}". '
                f"Must be of type str and one of the options \"{', '.join(options)}\"",
                slugs=[question.slug],
            )

    def _validate_question_dynamic_multiple_choice(
        self, question, value, info, **kwargs
    ):
        data_source = get_data_sources(dic=True)[question.data_source]
        if not data_source.validate:
            if not isinstance(value, list):
                raise CustomValidationError(
                    f'Invalid value: "{value}". Must be of type list',
                    slugs=[question.slug],
                )
            for v in value:
                if not isinstance(v, str):
                    raise CustomValidationError(
                        f'Invalid value: "{v}". Must be of type string',
                        slugs=[question.slug],
                    )
            return
        data = get_data_source_data(info, question.data_source)
        options = [d.slug for d in data]
        if not isinstance(value, list):
            raise CustomValidationError(
                f'Invalid value: "{value}". Must be of type list', slugs=[question.slug]
            )
        invalid_options = set(value) - set(options)
        if invalid_options:
            raise CustomValidationError(
                f'Invalid options "{invalid_options}". '
                f"Should be one of the options \"[{', '.join(options)}]\"",
                slugs=[question.slug],
            )

    def _validate_question_table(self, question, value, document, info, **kwargs):
        for _document in value:
            self._document_validator().validate(
                _document,
                parent=document,
                info=info,
                answer_tree=kwargs.get("answer_tree"),
            )

    def _document_validator(self):
        """Return instance of DocumentValidator.

        Configure the DocumentValidator according to our own config.
        """
        return DocumentValidator(do_check_required=self.do_check_required)

    def _validate_question_file(self, question, value, **kwargs):
        pass

    def validate(self, *, question, document, info, **kwargs):
        # Check all possible fields for value
        answer_tree = kwargs.pop("answer_tree", {})
        value = None
        for i in ["value", "file", "date", "documents"]:
            value = kwargs.get(i, value)
            if value:
                break

        # empty values are allowed
        # required check will be done in DocumentValidator
        if value:
            validate_func = getattr(self, f"_validate_question_{question.type}")
            validate_func(
                question, value, document=document, info=info, answer_tree=answer_tree
            )

        format_validators = get_format_validators(dic=True)
        for validator_slug in question.format_validators:
            format_validators[validator_slug]().validate(value, document)


class DocumentValidator:
    def __init__(self, do_check_required=True):
        self.do_check_required = do_check_required

    def validate(self, document, info, **kwargs):
        answer_tree = kwargs.get("answer_tree", {}) or self.get_document_answers(
            document
        )

        required_state = self.validate_required(document, answer_tree)

        # TODO: can we iterate over the entries in answer_tree here
        # so the loop doesn't hit the DB?
        for answer in document.answers.all():
            # If the question's "requiredness" evaluated to false,
            # we need to pass this along to sub validators, so they
            # won't complain if something is not provided "down there"
            required = required_state.get(answer.question.slug, True)

            further_check_required = required and self.do_check_required

            validator = AnswerValidator(further_check_required)
            if not isinstance(answer_tree[answer.question.slug], list):
                validator.validate(
                    document=document,
                    question=answer.question,
                    value=answer.value,
                    documents=answer.documents.all(),
                    info=info,
                    answer_tree=answer_tree[answer.question.slug],
                )
                continue

            for sub_tree in answer_tree[answer.question.slug]:
                validator.validate(
                    document=document,
                    question=answer.question,
                    value=answer.value,
                    documents=answer.documents.all(),
                    info=info,
                    answer_tree=sub_tree,
                )

    def get_document_answers(self, document, parent=None):
        doc_answers = document.answers.select_related("question").prefetch_related(
            "question__options"
        )

        questions = document.form.all_questions().values("slug", "type")

        # need to initialize here so we have a "parent" pointer to pass along
        answers = {}
        if parent is not None:
            answers["parent"] = parent

        answers.update(
            {
                ans.question_id: self._get_answer_value(ans, document, parent=answers)
                for ans in doc_answers
            }
        )

        # Create answer values for questions in the form that don't have
        # answers (yet)
        unanswered = {
            q["slug"]: self._get_answer_value(
                Answer(question_id=q["slug"], document=document),
                document,
                parent=answers,
            )
            for q in questions
            if q["slug"] not in answers
            and q["type"] not in [Question.TYPE_FORM, Question.TYPE_STATIC]
        }

        answers.update(unanswered)
        return answers

    def _get_answer_value(self, answer, document, parent):

        if answer.value is not None:
            return answer.value

        if answer.question.type in (
            Question.TYPE_DYNAMIC_MULTIPLE_CHOICE,
            Question.TYPE_MULTIPLE_CHOICE,
        ):
            # Unanswered multiple choice should return empty list
            # to denote emptyness
            return []

        elif answer.question.type == Question.TYPE_TABLE:
            # table type maps to list of dicts
            return [
                self.get_document_answers(document, parent=parent)
                for document in answer.documents.all()
            ]

        elif answer.question.type == Question.TYPE_FILE:
            return answer.file.name
        elif answer.question.type == Question.TYPE_DATE:
            return answer.date

        # Simple scalar types' value default to None in validation context
        elif answer.question.type in (
            Question.TYPE_INTEGER,
            Question.TYPE_FLOAT,
            Question.TYPE_TEXTAREA,
            Question.TYPE_TEXT,
            Question.TYPE_STATIC,
            Question.TYPE_DYNAMIC_CHOICE,
            Question.TYPE_CHOICE,
        ):
            return None

        else:  # pragma: no cover
            raise Exception(f"unhandled question type mapping {answer.question.type}")

    def validate_required(self, document, answer_tree):
        required_but_empty = []
        required_state = {}
        for question in document.form.all_questions().values(
            "slug", "is_required", "is_hidden"
        ):
            # TODO: can we iterate over questions of answers via answer_tree?
            try:
                expr = "is_required"
                is_required = (
                    jexl.QuestionJexl(answer_tree, document.form.slug).evaluate(
                        question["is_required"]
                    )
                    and self.do_check_required
                )

                expr = "is_hidden"
                is_hidden = jexl.QuestionJexl(answer_tree, document.form.slug).evaluate(
                    question["is_hidden"]
                )
                if is_required and not is_hidden:
                    if answer_tree.get(question["slug"], None) in EMPTY_VALUES:
                        required_but_empty.append(question["slug"])

                required_state[question["slug"]] = is_required
            except Exception as exc:
                expr_jexl = question.get(expr)
                log.error(
                    f"Error while evaluating {expr} expression on question {question['slug']}: "
                    f"{expr_jexl}: {str(exc)}"
                )
                raise RuntimeError(
                    f"Error while evaluating '{expr}' expression on question {question['slug']}: "
                    f"{expr_jexl}. The system log contains more information"
                )

        if required_but_empty and self.do_check_required:
            raise CustomValidationError(
                f"Questions {','.join(required_but_empty)} are required but not provided.",
                slugs=required_but_empty,
            )

        return required_state


class QuestionValidator:
    @staticmethod
    def _validate_format_validators(data):
        format_validators = data.get("format_validators")
        if format_validators:
            fv = get_format_validators(include=format_validators, dic=True)
            diff_list = list(set(format_validators) - set(fv))
            if diff_list:
                raise exceptions.ValidationError(
                    f"Invalid format validators {diff_list}."
                )

    @staticmethod
    def _validate_data_source(data_source):
        data_sources = get_data_sources(dic=True)
        if data_source not in data_sources:
            raise exceptions.ValidationError(f'Invalid data_source: "{data_source}"')

    def validate(self, data):
        if data["type"] in ["text", "textarea"]:
            self._validate_format_validators(data)
        if "dataSource" in data:
            self._validate_data_source(data["dataSource"])


def get_document_validity(document, info):
    validator = DocumentValidator()
    is_valid = True
    errors = []

    try:
        validator.validate(document, info)
    except CustomValidationError as exc:
        is_valid = False
        detail = str(exc.detail[0])
        errors = [{"slug": slug, "error_msg": detail} for slug in exc.slugs]

    return {"id": document.id, "is_valid": is_valid, "errors": errors}
