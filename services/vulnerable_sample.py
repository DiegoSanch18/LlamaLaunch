# Archivo de Prueba para el Auditor Local de Seguridad
import urllib3

# 1. Secreto expuesto
AWS_ACCESS_KEY_ID = "AKIAIOSFODNN7EXAMPLE" 
secret_token = "91a8e2b3c4d5e6f7g8h9"

def conectar_remoto(url):
    # 2. Deshabilitar SSL
    urllib3.disable_warnings()
    print(f"Conectando a {url}")

def ejecutar_entrada_usuario(entrada):
    # 3. Función sumamente crítica (RCE)
    return eval(entrada)

def funcion_compleja(x, y, z):
    # 4. Complejidad ciclomática inflada artificialmente
    res = 0
    if x > 10:
        res += 1
        if y < 5:
            res += 2
            if z == "test":
                res += 3
    else:
        if z == "run":
            res -= 1
            if y > 100:
                res -= 2
    return res
