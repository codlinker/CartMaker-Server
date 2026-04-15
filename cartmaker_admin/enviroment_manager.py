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
        "DEBUG":"Booleano que indica si Django se debe ejecutar en modo Debug. Debe ser \
            binario (0 o 1).",
        "API_VERSION":"Version de la API.",
        "JWT_SECRET_KEY":"Llave secreta para la firma de jwt.",
        "GOOGLE_OAUTH_CLIENT_ID":"Id client de la plataforma de Google Cloud necesaria \
            para usar la api de autenticacion de Google.",
        "GOOGLE_MAPS_API_KEY":"Api key de google maps.",
        "DOMAIN":"Dominio del proyecto.",
        "STORAGE_TYPE":"Almacenamiento que se utilizara para guardar toda la media con la \
            que interactuan los usuarios.",
        "AWS_ACCESS_KEY_ID":"Acces key id del bucket de AWS.",
        "AWS_SECRET_ACCESS_KEY":"Secret key del bucket de AWS.",
        "AWS_STORAGE_BUCKET_NAME":"Nombre del bucket de AWS.",
        "AWS_S3_REGION_NAME":"Region del bucket de AWS."
    }

    def __init__(self):
        self._db_name = None
        self._db_user = None
        self._db_pass = None
        self._db_host = None
        self._db_port = None
        self._secret_key = None
        self._jwt_secret_key = None
        self._debug = None
        self._api_version = None
        self._google_oauth_client_id = None
        self._google_maps_api_key = None
        self._domain = None
        self._storage_type = None
        self._aws_access_key_id = None
        self._aws_secret_access_key = None
        self._aws_storage_bucket_name = None
        self._aws_s3_region_name = None
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
    
    @property
    def JWT_SECRET_KEY(self) -> str:
        """
        Secret key de los Json Web Tokens
        """
        return self._jwt_secret_key
    
    @property
    def GOOGLE_OAUTH_CLIENT_ID(self) -> str:
        """
        ID Client de Google OAuth
        """
        return self._google_oauth_client_id
    
    @property
    def GOOGLE_MAPS_API_KEY(self) -> str:
        """
        API KEY de Google Maps.
        """
        return self._google_maps_api_key
    
    @property
    def DOMAIN(self) -> str:
        """
        Dominio del proyecto.
        """
        return self._domain
    
    @property
    def STORAGE_TYPE(self) -> str:
        """
        Almacenamiento que se utilizara para guardar toda la media con la que interactuan los usuarios.
        """
        return self._storage_type
    
    @property
    def AWS_ACCESS_KEY_ID(self) -> str:
        """
        Access key id del bucket de AWS.
        """
        return self._aws_access_key_id
    
    @property
    def AWS_SECRET_ACCESS_KEY(self) -> str:
        """
        Secret key del bucket de AWS.
        """
        return self._aws_secret_access_key
    
    @property
    def AWS_STORAGE_BUCKET_NAME(self) -> str:
        """
        Nombre del bucket de AWS.
        """
        return self._aws_storage_bucket_name
    
    @property
    def AWS_S3_REGION_NAME(self) -> str:
        """
        Region del bucket de AWS.
        """
        return self._aws_s3_region_name
    
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
            else:
                if env_variables[variable] == "STORAGE_TYPE":
                    if not env_variables[variable] in ['aws', 'local']:
                        print("********** ENVIROMENT MANAGER **********")
                        print(f"Tipo de almacenamiento {env_variables[variable]} no permitido.")
                        print("****************************************")
                        sys.exit()
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
            "API_VERSION":os.environ.get("API_VERSION"),
            "JWT_SECRET_KEY":os.environ.get("JWT_SECRET_KEY"),
            "GOOGLE_OAUTH_CLIENT_ID":os.environ.get('GOOGLE_OAUTH_CLIENT_ID'),
            "GOOGLE_MAPS_API_KEY":os.environ.get("GOOGLE_MAPS_API_KEY"),
            "DOMAIN":os.environ.get('DOMAIN'),
            "STORAGE_TYPE":os.environ.get('STORAGE_TYPE'),
            "AWS_ACCESS_KEY_ID":os.environ.get("AWS_ACCESS_KEY_ID"),
            "AWS_SECRET_ACCESS_KEY":os.environ.get('AWS_SECRET_ACCESS_KEY'),
            "AWS_STORAGE_BUCKET_NAME":os.environ.get("AWS_STORAGE_BUCKET_NAME"),
            "AWS_S3_REGION_NAME":os.environ.get("AWS_S3_REGION_NAME"),
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
        self._jwt_secret_key = env_variables['JWT_SECRET_KEY']
        self._google_oauth_client_id = env_variables['GOOGLE_OAUTH_CLIENT_ID']
        self._google_maps_api_key = env_variables['GOOGLE_MAPS_API_KEY']
        self._domain = env_variables['DOMAIN']
        self._storage_type = env_variables['STORAGE_TYPE']
        self._aws_access_key_id = env_variables['AWS_ACCESS_KEY_ID']
        self._aws_secret_access_key = env_variables['AWS_SECRET_ACCESS_KEY']
        self._aws_storage_bucket_name = env_variables['AWS_STORAGE_BUCKET_NAME']
        self._aws_s3_region_name = env_variables['AWS_S3_REGION_NAME']

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