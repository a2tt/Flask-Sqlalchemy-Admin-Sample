import math

from dominate.tags import *

from sqlalchemy import func
from sqlalchemy.inspection import inspect
from sqlalchemy.sql.sqltypes import Integer, Float, Boolean, String, DateTime

from project.models.base import User, AdminAccessLog

from project import db
import settings


def is_dev():
    return settings.STAGE == 'dev'


class Widget:
    def __init__(self):
        self.value = ''

    def __html__(self):
        pass


class ImageWidget(Widget):
    def __init__(self):
        raise NotImplementedError


class TextAreaWidget(Widget):
    def __init__(self, name, rows, cols=None, placeholder=None, disabled=False):
        super().__init__()
        self.name = self.id = name
        self.rows = rows
        self.cols = cols
        self.placeholder = placeholder if placeholder else f'{name}을 입력하세요.'
        self.disabled = disabled

    def __html__(self):
        tag = textarea(str(self.value),
                       id=self.id,
                       name=self.name,
                       rows=self.rows,
                       placeholder=self.placeholder
                       )
        if self.cols:
            tag.set_attribute('cols', self.cols)
        if self.disabled:
            tag.set_attribute('disabled', True)
        return tag


class SelectWidget(Widget):
    def __init__(self, name, options=None):
        super().__init__()
        self.name = self.id = name
        if not options:
            self.options = {'True': 1, 'False': 0}
        else:
            self.options = options

    def __html__(self):
        tag = select(id=self.id, name=self.name)
        tag.add(option('-----', value='', disabled=True,
                       hidden=True, selected=True if not str(self.value) else False))
        for key, value in self.options.items():
            opt = option(key, value=value)
            if str(self.value) == key or self.value == key:
                opt.set_attribute('selected', 1)
            tag.add(opt)
        return tag


class Paginator:
    def __init__(self, total_rows, page, per_page):
        self.per_page = per_page
        self.pages = self.last_page = math.ceil(total_rows / per_page)
        self.page = page
        self.near_pages = list(filter(lambda p: 0 < p <= self.pages, range(page - 3, page + 4)))

    @property
    def has_next(self):
        return self.page < self.last_page

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def prev_page(self):
        if self.has_prev:
            return self.page - 1
        return None

    @property
    def next_page(self):
        if self.has_next:
            return self.page + 1
        return None


class AdminModel:
    __tablename__ = None  # sqlalchemy.exc.NoForeignKeysError 방지

    per_page = 20
    __num_rows = None  # count(*)
    p_key = 'id'
    keys = []  # table rows
    list_display = []  # keys on list view
    search_keys = []  # 검색
    sort_keys = []  # sortable keys
    filter_keys = []  # filterable keys

    list_editable = []

    creatable = False
    editable = True
    deletable = False

    edit_role = User.ADMINS

    field_group = []  # detail view 에서 컬럼 그룹화

    class Meta:
        widgets = {}

    @classmethod
    def table_name(cls):
        return cls.__table__.name

    @classmethod
    def init(cls):
        cls.set_keys()
        cls.set_p_key()

    @classmethod
    def set_keys(cls):
        # cls.keys = inspect(cls).attrs.keys()  # backref 도 가져와버림. backref.type 값이 없어서 column_type 에서 에러
        cls.keys = cls.__table__.columns.keys()

    @classmethod
    def set_p_key(cls):
        ins = inspect(cls)
        cls.p_key = ins.primary_key[0].key

    @classmethod
    def num_rows(cls):
        """ 총 row 개수 """
        if not cls.__num_rows:
            return db.session.query(func.count(getattr(cls, cls.p_key))).scalar()
        else:  # ?? ... row 가 너무 많을 때 쓰려고 만든 것 같은데
            return cls.__num_rows

    @classmethod
    def column_type(cls, key, format_='py'):
        # print('---------------')
        # print(key)
        # print(getattr(cls, key))
        # print(type(getattr(cls, key)))
        if type(getattr(cls, key)) == property:  # FIXME :(
            type_ = String
        else:
            type_ = type(getattr(cls, key).type)

        if format_ == 'py':
            if type_ == Integer:
                return 'int'
            elif type_ == Float:
                return 'float'
            elif type_ == Boolean:
                return 'bool'
            elif type_ == DateTime:
                return 'str'
            else:  # str
                return 'str'
        elif format_ == 'html':
            if type_ in [Integer, Float]:
                return 'number'
            elif type_ == DateTime:
                # return 'datetime-local'
                return 'text'
            else:
                return 'text'
        return type_

    @classmethod
    def pagination(cls, page, pp, q_key=None, q=None):
        try:
            queryset = (db.session.query(cls))
            if q_key and q:
                type_ = cls.column_type(q_key, format_='py')
                if type_ in ['int', 'float']:
                    queryset = queryset.filter(getattr(cls, q_key) == q)
                else:
                    queryset = queryset.filter(getattr(cls, q_key).contains(q))
            items = (queryset.order_by(getattr(cls, cls.p_key).desc())
                     .offset((page - 1) * pp)
                     .limit(pp)
                     .all())
            return items
        except Exception as e:
            db.session.rollback()
            print(e)
            return cls.pagination(page, pp, None, None)

    @classmethod
    def sort_pagination(cls, page, pp, args):
        try:
            queryset = (db.session.query(cls))

            for key, value in args.items():
                if key not in cls.keys:
                    continue
                if value in ['desc', 'asc']:
                    queryset = (queryset.filter(getattr(cls, key).isnot(None))
                                .order_by(getattr(getattr(cls, key), value)()))

            items = (queryset.order_by(getattr(cls, cls.p_key).desc())
                     .offset((page - 1) * pp)
                     .limit(pp)
                     .all())
            return items
        except Exception as e:
            db.session.rollback()
            print(e)
            return []

    @classmethod
    def filter_pagination(cls, page, pp, args):
        # TODO 범위 쿼리
        try:
            queryset = (db.session.query(cls))

            for key, value in args.items():
                if key not in cls.keys:
                    continue
                type_ = cls.column_type(key, format_='py')
                if type_ == 'bool':
                    value = True if value == '1' else False
                    queryset = (queryset.filter(getattr(cls, key).is_(value)))
                elif type_ in ['int', 'float']:
                    queryset = (queryset.filter(getattr(cls, key) == value))
                else:  # str, DateTime
                    queryset = (queryset.filter(getattr(cls, key) == value))

            items = (queryset.order_by(getattr(cls, cls.p_key).desc())
                     .offset((page - 1) * pp)
                     .limit(pp)
                     .all())
            return items
        except Exception as e:
            db.session.rollback()
            print(e)
            return []


class UserAdmin(AdminModel, User):
    list_display = ['id', 'name', 'is_active', 'created_at']
    search_keys = ['id', 'name', 'role']
    sort_keys = ['id', 'name', 'created_at']
    filter_keys = ['is_active', 'role']

    creatable = True
    list_editable = ['name', 'is_active']
    if is_dev():
        list_editable += ['role']
    edit_role = [User.SUPERUSER]

    field_group = [
        ['id', 'is_active'],
        [],
        ['name', 'role', 'created_at'],
    ]

    class Meta:
        widgets = {
            'is_active': SelectWidget(name='is_active'),
            'role': SelectWidget(name='role',
                                 options={0: 0, 32: 32, 64: 64, 128: 128}),
        }


class AdminAccessLogAdmin(AdminModel, AdminAccessLog):
    list_display = ['id', 'user_id', 'endpoint', 'created_at']
    editable = False


# list view 생성
models = {
    'User': [UserAdmin],
    'Base': [AdminAccessLogAdmin],
}

# if is_dev():  # privacy!
#     models['Play'].insert(1, UserAdmin)

# list view 생성 (invisible)
hidden_models = []

auto_detail_views = [  # create DetailView
    AdminAccessLogAdmin,
]

auto_update_views = [
    UserAdmin, AdminAccessLogAdmin,
]

auto_create_views = [
    UserAdmin, AdminAccessLogAdmin,
]
