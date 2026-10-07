"""Run with python server.py --help. Local capstone server; use HTTPS for deployment."""
import argparse
import csv
import io
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from service import Service, Error

class Handler(BaseHTTPRequestHandler):
    service = None

    def handle_request(self):
        # Development and deployed servers share validation, cookies and security.
        from webapp import Application
        from urllib.parse import urlsplit
        parsed=urlsplit(self.path)
        environ={'REQUEST_METHOD':self.command,'PATH_INFO':parsed.path,
                 'QUERY_STRING':parsed.query,'CONTENT_LENGTH':self.headers.get('Content-Length',''),
                 'CONTENT_TYPE':self.headers.get('Content-Type',''),'wsgi.input':self.rfile,
                 'wsgi.url_scheme':'http','HTTP_HOST':self.headers.get('Host',''),
                 'HTTP_ORIGIN':self.headers.get('Origin',''),'HTTP_COOKIE':self.headers.get('Cookie',''),
                 'HTTP_AUTHORIZATION':self.headers.get('Authorization','')}
        self.connection.settimeout(30)
        def start_response(status,headers):
            self.send_response(int(status.split()[0]))
            for name,value in headers:self.send_header(name,value)
            self.end_headers()
        for body in Application(self.service)(environ,start_response):self.wfile.write(body)

    do_GET = handle_request
    do_POST = handle_request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db',default='movis.db')
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--mode',choices=['demo','yolo'],default='demo')
    parser.add_argument('--weights')
    parser.add_argument('--init',action='store_true')
    parser.add_argument('--seed-demo',action='store_true')
    args = parser.parse_args()
    service = Service(args.db,args.mode,args.weights)
    if args.init:
        from getpass import getpass
        service.bootstrap(input('Administrator username: '),getpass('Administrator password (12–128 characters): '),args.seed_demo)
        print('Database initialized. Run without --init to start the server.')
        return
    Handler.service = service
    print(f'MOVIS {args.mode.upper()} server at http://{args.host}:{args.port}. Demo detections are synthetic.')
    ThreadingHTTPServer((args.host,args.port),Handler).serve_forever()

if __name__ == '__main__':
    main()
