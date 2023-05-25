# Importa pacotes que serão utilizados
from datetime import datetime, timedelta
from pytz import timezone
from dotenv import load_dotenv
import os
from airflow import DAG
import airflow.utils.dates as airflow_date
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
import shutil

# Pastas temporarias onde irão ficar os dados que foram extraidos e os dados que foram tratados.
staging = "tmp/staging/"
refined = "tmp/refined/"


# Carrega as variaveis de ambiente definidas no arquivo ".env"
load_dotenv()

# Função de extração dos dados do bucket S3
def _extract():
    import boto3
    
    aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')

    # Configura as credenciais de acesso à conta da AWS
    s3 = boto3.resource('s3', aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key)


# Função de transformação dos dados, os deixando no padrão para serem enviados
def _transform():
    import pandas as pd
    import numpy as np
    

# Função de carregamento dos dados ja transformados para o banco Postgres
def _load():
    import psycopg2
    # Conecta com o banco de dados Postgres
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST'),
        database=os.environ.get('DB_NAME'),
        user=os.environ.get('DB_USER'),
        password=os.environ.get('DB_PASSWORD'),
        port = os.environ.get('DB_PORT'))
    
    # Cria um cursor para executar as instruções SQL
    cur = conn.cursor()
    
    # Adiciona os dados dos arquivos csv para o banco de dados
    cur.execute(f"""
       \copy client from '{refined}client.csv' DELIMITER ',' CSV HEADER 
    """)
    cur.execute(f"""
       \copy campaign from '{refined}campaign.csv' DELIMITER ',' CSV HEADER 
    """)
    cur.execute(f"""
       \copy economics from '{refined}economics.csv' DELIMITER ',' CSV HEADER
    """)
    
    # Aplica as alterações no banco de dados
    conn.commit()
    
    # Fecha conexão com o banco de dados
    cur.close()
    conn.close()
    
    # remove pasta temporaria
    shutil.rmtree("tmp", ignore_errors=False, onerror=None)

with DAG (
    dag_id="Pipeline ETL Marketing",
    description = 'Realiza a extração, tranformação e carga de dados de um bucket S3 para um banco de dados Postgres',
    start_date = airflow_date.days_ago(1),
    schedule_interval= "0 22 * * 6",
    tags=['Marketing','ETL'],
    
    
) as dag:
    
    extract = PythonOperator(
        task_id = 'extract_task',
        python_callable= _extract,
        email_on_failure= True,
        email = os.environ.get('EMAIL'),
        retries = 3,
        retry_delay = timedelta(minutes=5)
        
    )
    
    transform = PythonOperator(
        task_id = 'tansform_task',
        python_callable= _transform,
        email_on_failure= True,
        email = os.environ.get('EMAIL')
    )
    
    load = PythonOperator(
        task_id = 'load_task',
        python_callable= _load,
        email_on_failure= True,
        email = os.environ.get('EMAIL'),
        retries = 3,
        retry_delay = timedelta(minutes=5)
    )
    
    notify = EmailOperator(
        task_id = 'notify_task',
        email_on_failure= True,
        email = os.environ.get('EMAIL'), 
        to= os.environ.get('EMAIL'),
        subject='Pipeline Realizado Com Sucesso',
        html_content=f"<p> O Pipeline foi executado com sucesso as {str(datetime.now(timezone('America/Sao_Paulo')))}. <p>"
    )
    
    extract >> transform >> load >> notify
    
