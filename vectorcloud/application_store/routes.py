#!/usr/bin/env python3

import os
from flask import render_template, url_for, redirect, Blueprint, flash,\
    request, send_file
from vectorcloud import db
from vectorcloud.models import Status, ApplicationStore, Application, Settings
from vectorcloud.main.utils import get_stats
from vectorcloud.main.routes import sdk_version
from vectorcloud.application_store.forms import UploadPackage, AdminAdd
from vectorcloud.main.forms import SearchForm
from vectorcloud.application_store.utils import install_package,\
    export_package, clear_temp_folder

application_store = Blueprint('application_store', __name__)

curr_folder = os.path.dirname(os.path.realpath(__file__))
app_store_folder = os.path.join(curr_folder, 'application_store')
packages_folder = os.path.join(app_store_folder, 'packages')


@application_store.route("/app_store", methods=['GET', 'POST'])
def app_store():
    search_term = None
    num_results = 0
    clear_temp_folder()
    store_app_list = ApplicationStore.query.order_by(ApplicationStore.author)
    main_app_list = Application.query.all()

    for store_app in store_app_list:
        for main_app in main_app_list:
            if store_app.script_name.lower() == main_app.script_name.lower():
                store_app.installed = True
                db.session.merge(store_app)
                db.session.commit()
            else:
                store_app.installed = False

    err_msg = get_stats()
    if err_msg:
        return redirect(url_for('error_pages.' + err_msg))

    vector_status = Status.query.first()

    search_form = SearchForm()
    settings = Settings.query.first()

    if search_form.validate_on_submit():
        settings.search_by_name = search_form.by_name.data
        settings.search_by_description = search_form.by_description.data
        settings.search_by_author = search_form.by_author.data
        db.session.merge(settings)
        db.session.commit()
        search_term = search_form.search.data
        apps_searched = []

        if search_form.by_name.data is True:
            for application in store_app_list:
                if search_term.lower() in application.script_name.lower():
                    apps_searched.append(application.script_name)

        if search_form.by_description.data is True:
            for application in store_app_list:
                if search_term.lower() in application.description.lower():
                    apps_searched.append(application.script_name)

        if search_form.by_author.data is True:
            for application in store_app_list:
                if search_term.lower() in application.author.lower():
                    apps_searched.append(application.script_name)

        store_app_list = ApplicationStore.query.filter(
            ApplicationStore.script_name.in_(apps_searched))
        apps_searched = set(apps_searched)
        num_results = len(apps_searched)

    if request.method == 'GET':
        search_form.by_name.data = settings.search_by_name
        search_form.by_description.data = settings.search_by_description
        search_form.by_author.data = settings.search_by_author

    return render_template('applications/app_store.html',
                           title='App Store',
                           vector_status=vector_status,
                           sdk_version=sdk_version,
                           app_list=store_app_list,
                           search_form=search_form,
                           search_term=search_term,
                           num_results=num_results)


@application_store.route("/upload_package", methods=['GET', 'POST'])
def upload_package():
    form = UploadPackage()

    if form.validate_on_submit():
        if form.package.data:
            install_package(form.package.data)

        else:
            flash('No Package Uploaded!', 'warning')
        return redirect(url_for('application_store.upload_package'))

    return render_template('applications/install_package.html',
                           title='Install Package',
                           form=form)


@application_store.route("/app_store_admin_add", methods=['GET', 'POST'])
def app_store_admin_add():
    form = AdminAdd()
    app_list = ApplicationStore.query.all()

    if form.validate_on_submit():
        store_app = ApplicationStore(
            script_name=form.script_name.data,
            description=form.description.data,
            author=form.author.data,
            website=form.website.data,
            icon=form.icon.data,
            zip_file=form.zip_file.data,
        )
        db.session.add(store_app)
        db.session.commit()
        flash(form.script_name.data + ' added to app store.', 'success')
        return redirect(url_for('application_store.app_store_admin_add'))

    return render_template(
        'applications/app_store_admin_add.html', title='App Store - Admin',
        form=form, app_list=app_list)


@application_store.route("/edit_store_application/<script_id>",
                         methods=['GET', 'POST'])
def edit_store_application(script_id):
    form = AdminAdd()
    store_app = ApplicationStore.query.filter_by(id=script_id).first()

    if form.validate_on_submit():
        store_app.script_name = form.script_name.data
        store_app.author = form.author.data
        store_app.website = form.website.data
        store_app.description = form.description.data
        store_app.icon = form.icon.data
        store_app.zip_file = form.zip_file.data
        db.session.merge(store_app)
        db.session.commit()
        flash('App updated!', 'success')

    elif request.method == 'GET':
        form.script_name.data = store_app.script_name
        form.author.data = store_app.author
        form.website.data = store_app.website
        form.description.data = store_app.description
        form.icon.data = store_app.icon
        form.zip_file.data = store_app.zip_file

    return render_template(
        'applications/app_store_admin_edit.html', title='App Store - Admin',
        form=form, store_app=store_app)


@application_store.route("/delete_store_application/<script_id>",
                         methods=['GET', 'POST'])
def delete_store_application(script_id):
    db.session.query(ApplicationStore).filter_by(id=script_id).delete()
    db.session.commit()
    return redirect(url_for('application_store.app_store_admin_add'))


@application_store.route("/install_store_application/<script_id>",
                         methods=['GET', 'POST'])
def install_store_application(script_id):
    store_app = ApplicationStore.query.filter_by(id=script_id).first()
    applications = Application.query.all()

    if applications:
        for application in applications:
            if application.script_name.lower() == \
                    store_app.script_name.lower():
                flash('Application named "' + application.script_name +
                      '" already exists, please rename the existing \
                      application and try again.', 'warning')
                return redirect(url_for('application_store.app_store'))

    install_package(form_package=None,
                    store_package=store_app.zip_file,
                    override_output=True)
    store_app.installed = True
    db.session.merge(store_app)
    db.session.commit()
    flash(store_app.script_name + ' installed!', 'success')
    return redirect(url_for('application_store.app_store'))


@application_store.route("/export_application/<script_id>",
                         methods=['GET', 'POST'])
def export_application(script_id):
    zip_fn = export_package(script_id)
    return send_file(zip_fn)
    return redirect(url_for('main.home'))
