#!/usr/bin/env python3

import os
from sys import exit as sys_exit
from time import sleep, time
from grpc._channel import _Rendezvous
from pathlib import Path
from flask import flash, redirect, url_for
from configparser import ConfigParser
from vectorcloud.models import Command, Output, Status, ApplicationStore,\
    Settings
from vectorcloud.paths import list_folder
from vectorcloud import db

try:
    import anki_vector
    from anki_vector.util import degrees, radians
except ImportError:
    sys_exit("Cannot import from anki_vector: Install per Anki instructions")


# establishes routes decorated w/ @public_route as accessible while not signed
# in. See login and register routes for usage
def public_route(decorated_function):
    decorated_function.is_public = True
    return decorated_function


# initiate config parser
config = ConfigParser()


# ------------------------------------------------------------------------------
# Main functions
# ------------------------------------------------------------------------------

# get_stats(): this function gets the results of robot.get_version_state() &
# robot.get_battery_state() and stores it to the status table in the database
# it clears the table at the begining of the function and leaves the data there
# until it is called again.
def get_stats(force=False):
    try:
        status = Status.query.first()
        timestamp = time()

        if status is None:
            new_stamp = timestamp - 20
            status = Status(timestamp=new_stamp)
            db.session.add(status)
            db.session.commit()

        elif timestamp - status.timestamp > 15 or force is True:

            # get robot name and ip from config file
            home = Path.home()
            sdk_config_file = os.path.join(home, '.anki_vector',
                                           'sdk_config.ini')
            f = open(sdk_config_file)
            serial = f.readline()
            serial = serial.replace(']', '')
            serial = serial.replace('[', '')
            serial = serial.replace('\n', '')
            f.close()
            config.read(sdk_config_file)
            ip = config.get(serial, 'ip')
            name = config.get(serial, 'name')

            # get results from battery state and version state,
            # save to database
            args = anki_vector.util.parse_command_args()
            with anki_vector.Robot(args.serial,
                                   requires_behavior_control=False,
                                   cache_animation_list=False) as robot:

                version_state = robot.get_version_state()
                battery_state = robot.get_battery_state()

                db.session.query(Status).delete()
                status = Status(version=version_state.os_version,
                                battery_voltage=battery_state.battery_volts,
                                battery_level=battery_state.battery_level,
                                status_charging=battery_state.is_on_charger_platform,
                                cube_battery_level=battery_state.cube_battery.level,
                                cube_id=battery_state.cube_battery.factory_id,
                                cube_battery_volts=battery_state.
                                cube_battery.battery_volts,
                                timestamp=timestamp,
                                ip=ip,
                                name=name)
                db.session.add(status)
                db.session.commit()

        else:
            status.timestamp = timestamp
            db.session.merge(status)
            db.session.commit()

    except _Rendezvous:
        sleep(3)
        get_stats(force=True)

    except anki_vector.exceptions.VectorNotFoundException:
        return 'vector_not_found'

    except anki_vector.exceptions.VectorControlTimeoutException:
        return 'vector_stuck'

    except Exception:
        return 'multiple_vectors'


# robot_do(): this function executes all commands in the command table in order
# with the condition of with anki_vector.Robot(args.serial) as robot:
# if there are commands in the commands in the command table, all you have to
# do to execute is redirect to /execute_commands/ and this function will be
# called. Output is sent to a flash message.
def robot_do(override_output=None):
    robot_commands = Command.query.all()
    try:
        args = anki_vector.util.parse_command_args()
        with anki_vector.Robot(args.serial, enable_camera_feed=True) as robot:

            for command in robot_commands:
                command_string = str(command)
                robot_output_string = str(eval(command_string))
                db_output = Output(output=robot_output_string)
                db.session.add(db_output)
                db.session.commit()

            command_output = Output.query.all()

            if override_output:
                flash(override_output, 'success')
                func_out = override_output

            else:
                for out in command_output:
                    if out is None:
                        pass
                    else:
                        out_string = 'Command completed successfully! Output: \
                            ' + str(out)
                        flash(out_string, 'success')
                        func_out = out_string

    except NameError:
        flash('Command not found!', 'warning')
        func_out = 'Command not found!'

    except anki_vector.exceptions.VectorNotFoundException:
        func_out = 'vector_not_found'

    except anki_vector.exceptions.VectorControlTimeoutException:
        func_out = 'vector_stuck'

    db.session.query(Command).delete()
    db.session.query(Output).delete()
    db.session.commit()

    return func_out


def database_init():

    # Create the settings table if it doesn't exist
    settings = Settings.query.first()
    if not settings:
        settings = Settings(id=1)
        db.session.add(settings)
        db.session.commit()

    # Initialize app store table
    db.session.query(ApplicationStore).delete()
    db.session.commit()

    store_app_list = os.listdir(list_folder)

    for app_name in store_app_list:
        app_path = os.path.join(list_folder, app_name)
        f = open(app_path)
        name = f.readline()
        name = name.replace(']', '')
        name = name.replace('[', '')
        name = name.replace('\n', '')
        f.close()
        config.read(app_path)
        icon = config.get(name, 'icon')
        description = config.get(name, 'description')
        author = config.get(name, 'author')
        website = config.get(name, 'website')
        zip_file = config.get(name, 'zip_file')

        store_app = ApplicationStore(script_name=name,
                                     author=author,
                                     website=website,
                                     description=description,
                                     icon=icon,
                                     installed=False,
                                     zip_file=zip_file)

        db.session.add(store_app)
        db.session.commit()


def undock_robot():
    db.session.query(Command).delete()
    robot_command = Command(command='robot.behavior.drive_off_charger()')
    db.session.add(robot_command)
    db.session.commit()

    override_message = 'Undock Command Complete!'
    err_msg = robot_do(override_output=override_message)
    if err_msg != override_message:
        db.session.query(Command).delete()
        db.session.commit()
        return redirect(url_for('error_pages.' + err_msg))

    err_msg = get_stats(force=True)
    if err_msg:
        return redirect(url_for('error_pages.' + err_msg))


def dock_robot():
    db.session.query(Command).delete()
    robot_command = Command(command='robot.behavior.drive_on_charger()')
    db.session.add(robot_command)
    db.session.commit()

    override_message = 'Dock Command Complete!'
    err_msg = robot_do(override_output=override_message)
    if err_msg != override_message:
        db.session.query(Command).delete()
        db.session.commit()
        return redirect(url_for('error_pages.' + err_msg))

    err_msg = get_stats(force=True)
    if err_msg:
        return redirect(url_for('error_pages.' + err_msg))


def robot_connect_cube():
    db.session.query(Command).delete()
    robot_command = Command(command='robot.world.connect_cube()')
    db.session.add(robot_command)
    db.session.commit()

    override_message = 'Cube Connected!'
    err_msg = robot_do(override_output=override_message)
    if err_msg != override_message:
        return redirect(url_for('error_pages.' + err_msg))


def robot_dock_cube():
    args = anki_vector.util.parse_command_args()
    with anki_vector.Robot(args.serial) as robot:
        robot.behavior.drive_off_charger()
        cube = robot.world.connect_cube()
        if cube:
            robot.behavior.dock_with_cube(cube)
            robot.behavior.set_lift_height(100.0)
            sleep(5)
            robot.behavior.set_lift_height(0,  max_speed=10.0)
            robot.world.disconnect_cube()
            flash('Cube picked up!', 'success')


def execute_db_commands():
    robot_commands = Command.query.all()
    if robot_commands:
        err_msg = robot_do()
        if err_msg:
            return err_msg

    else:
        flash('No command staged!', 'warning')
