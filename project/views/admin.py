import json
import re
import functools

from flask import Blueprint, g, request, current_app, redirect, url_for, \
    render_template, abort, flash, session

from project.models.admin import *

from project.utils import *

import settings

bp = Blueprint('admin', __name__, template_folder='../templates', static_folder='static')


def super_user_required(func):
    @functools.wraps(func)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if user_id:
            user = db.session.query(User).get(user_id)
            g.current_user = user
            if user and user.role in [User.SUPERUSER]:
                return func(*args, **kwargs)
            else:
                flash('권한이 없습니다.', 'warning')
                return '<script>window.history.back();</script>'
        return func(*args, **kwargs)

    return decorated


@bp.before_request
def admin_required():
    g.current_user = None
    return  # FIXME
    user_id = session.get('user_id')
    if not user_id:
        session['next'] = request.url
        return redirect(url_for('user.login'))
    user = db.session.query(User).get(user_id)
    if user and user.role in User.ADMINS:
        g.current_user = user
    else:
        abort(404)


@bp.before_request
def update_view_auth():
    return  # FIXME
    view = request.endpoint.replace(f'{request.blueprint}.', '')
    if settings.STAGE == 'production':
        if view.endswith('_update') and request.method in ['POST', 'PUT', 'DELETE']:
            idx = view.rindex('_update')
            model_name = snake_to_camel(view[:idx]) + 'Admin'
            model = globals()[model_name]
            if g.current_user is None:  # 왜??
                session['next'] = request.url
                return redirect(url_for('user.login'))
            if g.current_user.role not in model.edit_role:
                flash('권한이 부족합니다.', 'error')
                return redirect(request.url.replace('update', 'detail'))


@bp.before_request
def logging():
    if settings.STAGE == 'production':
        if request.method == 'POST' or (request.endpoint.endswith('_list') and not request.args.get('page')):
            log = AdminAccessLog(user_id=g.current_user.id if g.current_user else 0,
                                 endpoint=request.endpoint,
                                 args=json.dumps(dict(request.args)),
                                 form=json.dumps(dict(request.form)))
            db.session.add(log)
            db.session.commit()


@bp.before_request
def inject_stage():
    g.stage = settings.STAGE


def get_py_type(column):
    type_ = type(column.type)
    if type_ == Integer:
        return 'int'
    elif type_ == Float:
        return 'float'
    elif type_ == Boolean:
        return 'bool'
    # elif type_ == Enum:
    #     return 'enum'
    else:
        return 'str'


def calc_wide(fields):
    wide = int(16 / len(fields))
    map_ = {
        1: 'one', 2: 'two', 3: 'three', 4: 'four',
        5: 'five', 6: 'six', 7: 'seven', 8: 'eight',
        9: 'nine', 10: 'ten', 11: 'eleven', 12: 'twelve',
        13: 'thirteen', 14: 'fourteen', 15: 'fifteen', 16: 'sixteen',
    }
    return map_.get(wide)


@bp.context_processor
def admin_context_processor():
    return {'getattr': getattr,
            'py_type': get_py_type,
            'models': models,
            'calc_wide': calc_wide,
            }


@bp.route('/')
def index():
    return redirect(url_for('admin.user_list'))


def manage_model(model):
    def wrapper(func):
        @functools.wraps(func)
        def decorated_function(*args, **kwargs):
            try:
                model.init()
                search = request.args.get('search')

                page = int(request.args.get('page', 1))  # common
                pp = int(request.args.get('pp', model.per_page))  # common
                paginator = Paginator(model.num_rows(), page, pp)  # common

                if not search:  # 그냥
                    q_key = request.args.get('q_key', None)
                    q = request.args.get('q', None)
                    items = model.pagination(page, pp, q_key, q)  # normal query
                elif search == 'sort':
                    items = model.sort_pagination(page, pp, dict(request.args))
                elif search == 'filter':
                    items = model.filter_pagination(page, pp, dict(request.args))
                else:
                    items = models.pagination(page, pp)

                keys = model.keys
                display_keys = model.list_display
                search_keys = model.search_keys
                sort_keys = model.sort_keys
                filter_keys = model.filter_keys

                return render_template('admin/default/item_list.html',
                                       model=model,
                                       model_name=model.table_name(),
                                       items=items,
                                       keys=keys, display_keys=display_keys,
                                       search_keys=search_keys, sort_keys=sort_keys, filter_keys=filter_keys,
                                       page=page, paginator=paginator)
            except Exception as e:
                db.session.rollback()
                current_app.logger.exception(e)
                abort(500)

        return decorated_function

    return wrapper


def list_view_generator(model):
    @manage_model(model)
    def view():
        pass

    return view


def detail_view_generator(model):
    def view(p_key):
        model.init()
        item = db.session.query(model).get(p_key)
        for key, widget in item.Meta.widgets.items():
            widget.value = getattr(item, key)

        return render_template(f'admin/default/detail_view.html',
                               model=model, item=item)

    return view


def update_view_generator(model):
    def view(p_key):
        model.init()
        item = db.session.query(model).get(p_key)

        data = dict(request.form)
        for key, value in data.items():
            if key not in model.list_editable:  # 수정 가능한 것들만
                continue
            type_ = model.column_type(key, format_='py')
            if type_ == 'bool':
                value = True if value in [1, '1', 'true'] else False
            setattr(item, key, value)

        db.session.add(item)
        db.session.commit()

        flash('성공', 'success')
        return redirect(url_for(f'admin.{model.table_name()}_detail', p_key=p_key))

    return view


def create_view_generator(model):
    @super_user_required
    def view():
        if request.method == 'GET':
            model.init()
            return render_template('admin/default/create_view.html',
                                   model=model)
        else:
            try:
                data = dict(request.form)
                for key, value in data.items():
                    type_ = model.column_type(key, format_='py')
                    if type_ == 'bool':
                        data[key] = True if value in [1, '1', 'true'] else False

                item = model(**data)
                db.session.add(item)
                db.session.commit()

                p_key = getattr(item, item.p_key)
                flash('성공', 'success')
                return redirect(url_for(f'admin.{model.table_name()}_detail', p_key=p_key))
            except Exception as e:
                flash(re.sub('''[\"\']+''', '`', str(e).replace('\n', ' ')), 'error')
                return '''<script>window.history.back();</script>'''

    return view


# list view (모든 admin model 통합)
for category, models_ in models.items():
    for model in models_:
        bp.add_url_rule(f'/{model.table_name()}', f'{model.table_name()}_list', list_view_generator(model))
for model in hidden_models:
    bp.add_url_rule(f'/{model.table_name()}', f'{model.table_name()}_list', list_view_generator(model))

# detail view
for model in auto_detail_views:
    bp.add_url_rule(f'/{model.table_name()}/<p_key>/detail', f'{model.table_name()}_detail',
                    detail_view_generator(model))

# update view
for model in auto_update_views:
    bp.add_url_rule(f'/{model.table_name()}/<p_key>/update', f'{model.table_name()}_update',
                    update_view_generator(model), methods=['POST'])

# create view
for model in auto_create_views:
    bp.add_url_rule(f'/{model.table_name()}/create', f'{model.table_name()}_create',
                    create_view_generator(model), methods=['GET', 'POST'])


@bp.route('/user/<p_key>/detail')
def user_detail(p_key):
    model = UserAdmin
    model.init()
    item = db.session.query(model).get(p_key)
    for key, widget in item.Meta.widgets.items():
        widget.value = getattr(item, key)
    return render_template(f'admin/models/user.html',
                           model=model, item=item)


@bp.route('/management')
def manage():
    return 'management'
