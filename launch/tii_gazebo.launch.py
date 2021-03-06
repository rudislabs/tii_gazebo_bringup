from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import SetLaunchConfiguration
from launch.actions import SetEnvironmentVariable
from launch.actions import IncludeLaunchDescription
from launch.actions import ExecuteProcess
from launch.actions import LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import EnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from os import getlogin
from time import sleep
import json
import numpy as np

user_name = str(getlogin())

# Default path to world file
default_world_path = '/home/{:s}/git/tii_gazebo/worlds/abu_dhabi.world'.format(user_name)

# Path to PX4 binary (in this case _sitl_default, could also be _sitl_rtps)
px4_path = '/home/{:s}/git/PX4-Autopilot/build/px4_sitl_default'.format(user_name)

with open('/home/{:s}/git/tii_gazebo/scripts/gen_params.json'.format(user_name)) as json_file:
    sim_params = json.load(json_file)

models = sim_params["models"]

latitude = sim_params["world_params"]["latitude"]
longitude = sim_params["world_params"]["longitude"]
altitude = sim_params["world_params"]["altitude"]

def generate_launch_description():

    

    
    ld = LaunchDescription([
    	# World path argument
        DeclareLaunchArgument(
            'world_path', default_value= default_world_path,
            description='Provide full world file path and name'),
        LogInfo(msg=LaunchConfiguration('world_path')),
        ])

    # Get path to gazebo package
    gazebo_package_prefix = get_package_share_directory('gazebo_ros')

    # Launch gazebo servo with world file from world_path
    gazebo_server = IncludeLaunchDescription(
                PythonLaunchDescriptionSource([gazebo_package_prefix,'/launch/gzserver.launch.py']),
                launch_arguments={'world': LaunchConfiguration('world_path')}.items(),
                )
    
    ld.add_action(gazebo_server)

    instance = 0
    for model_params in models:

        base_model = str(models[model_params]["base_model"])
        spawn_pose = models[model_params]["spawn_pose"]
        sdf_version = str(models[model_params]["sdf_version"])
        mavlink_tcp_port = str(models[model_params]["mavlink_tcp_port"])
        mavlink_udp_port = str(models[model_params]["mavlink_udp_port"])
        qgc_udp_port = str(models[model_params]["qgc_udp_port"])
        sdk_udp_port = str(models[model_params]["sdk_udp_port"])
        serial_enabled = str(models[model_params]["serial_enabled"])
        serial_device = str(models[model_params]["serial_device"])
        serial_baudrate = str(models[model_params]["serial_baudrate"])
        enable_lockstep = str(models[model_params]["enable_lockstep"])
        hil_mode = str(models[model_params]["hil_mode"])
        sdf_output_path = str(models[model_params]["output_path"])
        config_file = str(models[model_params]["config_file"])

        if models[model_params]["model_name"] == "NotSet":
            model_name = 'sitl_tii_{:s}_{:d}'.format(base_model,instance)
        else: 
            model_name = models[model_params]["model_name"]

        if sdf_output_path == "0":
            sdf_output_path = "/tmp"

        # Path for PX4 binary storage
        sitl_output_path = '/tmp/{:s}'.format(model_name)

        generate_args = '''--base_model "{:s}" --sdf_version "{:s}" --mavlink_tcp_port "{:s}" 
            --mavlink_udp_port "{:s}" --qgc_udp_port "{:s}" --sdk_udp_port "{:s}" 
            --serial_enabled "{:s}" --serial_device "{:s}" --serial_baudrate "{:s}" 
            --enable_lockstep "{:s}" --hil_mode "{:s}" --model_name "{:s}" 
            --output_path "{:s}" --config_file "{:s}"'''.format(
            base_model, sdf_version, mavlink_tcp_port, 
            mavlink_udp_port, qgc_udp_port, sdk_udp_port,
            serial_enabled, serial_device, serial_baudrate, 
            enable_lockstep, hil_mode, model_name, 
            sdf_output_path, config_file).replace("\n","").replace("    ","")

        generate_model = ['''python3 /home/{:s}/git/tii_gazebo/scripts/jinja_model_gen.py 
            {:s}'''.format(user_name, generate_args).replace("\n","").replace("    ","")]

        # Command to make storage folder
        sitl_folder_cmd = ['mkdir -p \"{:s}\"'.format(sitl_output_path)]

        latitude_vehicle = float(latitude) + ((float(spawn_pose[1])/6378137.0)*(180.0/np.pi))
        longitude_vehicle = float(longitude) + ((float(spawn_pose[0])/
            (6378137.0*np.cos((np.pi*float(latitude))/180.0)))*(180.0/np.pi))
        altitude_vehicle = float(altitude) + float(spawn_pose[2])
        

        px4_env = '''export PX4_SIM_MODEL=\"{:s}\"; export PX4_HOME_LAT={:s}; 
                        export PX4_HOME_LON={:s}; export PX4_HOME_ALT={:s};'''.format(
                        base_model, str(latitude_vehicle), str(longitude_vehicle), 
                        str(altitude_vehicle)).replace("\n","").replace("    ","")

        # Command to export model and run PX4 binary         
        px4_cmd = '''{:s} eval \"\"{:s}/bin/px4\" 
            -w {:s} \"{:s}/etc\" -s etc/init.d-posix/rcS -i {:d}\"; bash'''.format(
                px4_env, px4_path, sitl_output_path, px4_path, instance)

        # Xterm command to name xterm window and run px4_cmd
        xterm_px4_cmd = ['''xterm -hold -T \"PX4 NSH {:s}\" 
            -n \"PX4 NSH {:s}\" -e \'{:s}\''''.format(
                sitl_output_path, sitl_output_path,
                px4_cmd).replace("\n","").replace("    ","")]

        jinja_generate = ExecuteProcess(
            cmd=generate_model,
            name='jinja_gen_{:s}'.format(model_name),
            shell=True,
            output='screen')

        ld.add_action(jinja_generate)

        # Make storage command
        make_sitl_folder = ExecuteProcess(
            cmd=sitl_folder_cmd,
            name='make_sitl_folder_{:s}'.format(model_name),
            shell=True)
    
        ld.add_action(make_sitl_folder)

        # Run PX4 binary
        px4_posix = ExecuteProcess(
            cmd=xterm_px4_cmd,
            name='xterm_px4_nsh_{:s}'.format(model_name),
            shell=True)
    
        ld.add_action(px4_posix)

        # GAZEBO_MODEL_PATH has to be correctly set for Gazebo to be able to find the model
        spawn_entity = Node(package='gazebo_ros', executable='spawn_entity.py',
                        arguments=['-entity', '{:s}'.format(model_name),
                            '-x', str(spawn_pose[0]), '-y', str(spawn_pose[1]), '-z', str(spawn_pose[2]),
                            '-R', str(spawn_pose[3]), '-P', str(spawn_pose[4]), '-Y', str(spawn_pose[5]),
                            '-file', '{:s}/{:s}.sdf'.format(sdf_output_path, model_name)],
                        name='spawn_{:s}'.format(model_name), output='screen')

        ld.add_action(spawn_entity)
        instance += 1

    # Launch gazebo client
    gazebo_client = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([gazebo_package_prefix,'/launch/gzclient.launch.py']))
    
    LogInfo(msg="\nWaiting to launch Gazebo Client...\n")
    sleep(2)

    ld.add_action(gazebo_client)

    return ld
