from myapp import create_app
import os




if __name__=='__main__':
    app = create_app()
    debug_mode = os.getenv('DEBUG', 'False').lower() in ['true', '1', 't']
    app.run(host='0.0.0.0', debug=debug_mode)

