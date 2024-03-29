import mimetypes
import socket
import logging
from urllib.parse import unquote_plus, urlparse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
from pymongo.mongo_client import MongoClient
from datetime import datetime

# MongoDB URI
URI = "mongodb://mongodb:27017"
# Base directory for serving files
BASE_DIR = Path(__file__).parent
# Buffer size for socket communication
BUFFER_SIZE = 1024
# HTTP server configuration
HTTP_PORT = 3000
HTTP_HOST = ''
# Socket server configuration
SOCKET_HOST = '127.0.0.1'
SOCKET_PORT = 5000


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Routing
        router = urlparse(self.path).path
        match router:
            case "/":
                self.send_html("index.html")
            case "/message":
                self.send_html('message.html')
            case _:
                # Serve static files if exists, otherwise error page
                file = BASE_DIR.joinpath(router[1:])
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html("error.html", 404)

    def do_POST(self):
        # Handle POST request
        size = self.headers.get("Content-Length")
        data = self.rfile.read(int(size)).decode()

        # Send data to socket server
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.sendto(data.encode(), (SOCKET_HOST, SOCKET_PORT))
        client_socket.close()

        # Redirect to home page after POST
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_html(self, filename, status=200):
        # Serve HTML files
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open(filename, "rb") as f:
            self.wfile.write(f.read())

    def send_static(self, filename, status=200):
        # Serve static files with correct MIME type
        self.send_response(status)
        mimetype = mimetypes.guess_type(filename)[0] if mimetypes.guess_type(filename)[
            0] else "text/plain"
        self.send_header("Content-type", mimetype)
        self.end_headers()
        with open(filename, "rb") as f:
            self.wfile.write(f.read())


def save_data(data):
    # Save data to MongoDB
    client = MongoClient(URI)
    db = client.homework
    parse_data = unquote_plus(data.decode())
    try:
        # Parse and insert data
        parse_data = {key: value for key, value in [
            el.split("=") for el in parse_data.split("&")]}
        parse_data["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        db.homework.insert_one(parse_data)
    except ValueError as e:
        logging.error(f"Parse error: {e}")
    except Exception as e:
        logging.error(f"Failed to save: {e}")
    finally:
        client.close()


def run_http_server():
    # Start HTTP server
    httpd = HTTPServer((HTTP_HOST, HTTP_PORT), HttpHandler)
    try:
        logging.info(f"Server started on http://{HTTP_HOST}:{HTTP_PORT}")
        httpd.serve_forever()
    except Exception as e:
        logging.error(f"Server error: {e}")
    finally:
        logging.info("Server stopped")
        httpd.server_close()


def run_socket_server():
    # Start socket server
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((SOCKET_HOST, SOCKET_PORT))
    logging.info(f"Server started on socket://{SOCKET_HOST}:{SOCKET_PORT}")
    try:
        while True:
            data, addr = sock.recvfrom(BUFFER_SIZE)
            logging.info(f"Received message from {addr}: {data.decode()}")
            save_data(data)
    except Exception as e:
        logging.error(f"Server error: {e}")
    finally:
        logging.info("Server stopped")
        sock.close()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(process)s - %(message)s")

    print('working')
    # Start servers in separate processes
    http_process = Process(target=run_http_server, name="HTTP Server")
    print('working2')
    socket_process = Process(target=run_socket_server, name="Socket Server")

    # Start processes
    http_process.start()
    socket_process.start()

    # Wait for processes to finish
    http_process.join()
    socket_process.join()
