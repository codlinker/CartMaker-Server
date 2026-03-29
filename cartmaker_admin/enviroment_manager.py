import os
import sys

class EnviromentManager:
    """ Controlador de variables de entorno. """

    ENV_VARIABLES_DESCRIPTION = {
        "DB_NAME":"Nombre de la base de datos PostgreSQL (ej: cartmaker_local_db).",
        "DB_USER":"Usuario dueño de la base de datos con permisos de esquema.",
        "DB_PASSWORD":"Contraseña de acceso para el usuario de la base de datos.",
        "DB_HOST":"Host de la base de datos.",
        "DB_PORT":"Puerto de la base de datos.",
        "DJANGO_SECRET_KEY":"Llave secreta para la seguridad y criptografía de Django.",
        "DEBUG":"Booleano que indica si Django se debe ejecutar en modo Debug. Debe ser binario (0 o 1).",
        "API_VERSION":"Version de la API."
    }

    def __init__(self):
        self._db_name = None
        self._db_user = None
        self._db_pass = None
        self._db_host = None
        self._db_port = None
        self._secret_key = None
        self._debug = None
        self._api_version = None
        self.__execute_sh_file()
        self.__load_enviroment_variables()

    @property
    def DB_NAME(self) -> str:
        """ Nombre de la base de datos PostgreSQL (ej: cartmaker_local_db). """
        return self._db_name

    @property
    def DB_USER(self) -> str:
        """ Usuario dueño de la base de datos con permisos de esquema. """
        return self._db_user
    
    @property
    def DB_HOST(self) -> str:
        """ Host de la base de datos. """
        return self._db_host
    
    @property
    def DB_PORT(self) -> str:
        """ Puerto de la base de datos. """
        return self._db_port

    @property
    def DB_PASSWORD(self) -> str:
        """ Contraseña de acceso para el usuario de la base de datos. """
        return self._db_pass

    @property
    def DJANGO_SECRET_KEY(self) -> str:
        """ Llave secreta para la seguridad y criptografía de Django. """
        return self._secret_key
    
    @property
    def DEBUG(self) -> bool:
        """ Booleano que indica si Django se debe ejecutar en modo Debug. """
        return self._debug
    
    @property
    def API_VERSION(self) -> str:
        """ Version de la API. """
        return self._api_version
    
    def __get_env_variable_description(self, env_variable_name:str)->str:
        """
        Retorna una descripcion para la variable indicada.
        """
        description = self.ENV_VARIABLES_DESCRIPTION[env_variable_name]
        return description if description else "No se encontro descripcion para la variable."

    def __check_variables(self, env_variables:dict):
        """
        Checkea que cada variable se haya cargado correctamente.
        Si hay variables que faltan, las notifica y rompe la ejecucion.
        """
        missing_variables = []
        for variable in env_variables:
            if env_variables[variable] is None:
                missing_variables.append(variable)
        if len(missing_variables) > 0:
            print("********** ENVIROMENT MANAGER **********")
            for missing_variable in missing_variables:
                print(f"\nFalta la variable de entorno '{missing_variable}': {self.__get_env_variable_description(missing_variable)}")
            print("\nTerminando ejecucion...\n")
            print("****************************************")
            sys.exit()

    def __load_enviroment_variables(self)->dict:
        """
        Carga las variables de entorno del sistema,
        ejecuta el chequeo de las mismas y llena
        las variables de la clase con sus valores correspondientes..
        """
        env_variables = {
            # Credenciales de BD
            "DB_NAME":os.environ.get('DB_NAME'),
            "DB_USER":os.environ.get('DB_USER'),
            "DB_PASSWORD":os.environ.get('DB_PASSWORD'),
            "DB_HOST":os.environ.get('DB_HOST'),
            "DB_PORT":os.environ.get('DB_PORT'),
            # Credenciales de Django
            "DJANGO_SECRET_KEY":os.environ.get("DJANGO_SECRET_KEY"),
            "DEBUG":self.__process_boolean_env_variable(os.environ.get('DEBUG')),
            "API_VERSION":os.environ.get("API_VERSION")
        }
        self.__check_variables(env_variables)
        self._db_name = env_variables['DB_NAME']
        self._db_user = env_variables['DB_USER']
        self._db_pass = env_variables['DB_PASSWORD']
        self._db_host = env_variables['DB_HOST']
        self._db_port = env_variables['DB_PORT']
        self._secret_key = env_variables['DJANGO_SECRET_KEY']
        self._debug = env_variables['DEBUG']
        self._api_version = env_variables['API_VERSION']

    def __process_boolean_env_variable(self, variable:str)->bool:
        """Procesa la variable indicada en el parametro. Se espera
        que sea un string y que pueda ser parseable a int siendo un
        numero binario (0 o 1). Retorna un booleano o None si algo falla."""
        if variable is None:
            return None
        try:
            return bool(int(variable))
        except Exception as e:
            print(f"Error al procesar la variable de entorno booleana '{variable}': {e}")
            return None
        
    def __execute_sh_file(self):
        """ Lee el archivo .sh de variables de entorno y 
        carga las variables en os.environ """
        if os.path.exists("variables.sh"):
            with open("variables.sh", 'r') as f:
                for line in f:
                    # Limpiamos la línea y omitimos comentarios o líneas vacías
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Quitamos el prefijo 'export ' si existe
                    if line.startswith('export '):
                        line = line.replace('export ', '', 1)
                    
                    if '=' in line:
                        key, value = line.split('=', 1)
                        # Quitamos comillas si las tienen
                        value = value.strip("'").strip('"')
                        os.environ[key.strip()] = value
        else:
            print("********** ENVIROMENT MANAGER **********\n")
            print("No se encontro el archivo variables.sh\n\nAsegurese de incluirlo en la ruta principal del proyecto.")
            print("\n****************************************")
            sys.exit()