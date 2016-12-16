#!/usr/bin/env python3

if __name__ == "__main__":

    import argparse
    from app import create_app
    app = create_app()

    parser = argparse.ArgumentParser()
    parser.add_argument('-i',
                        '--host',
                        default=app.config['DEFAULT_HOST'],
                        help='Specify IP address or localhost.')
    parser.add_argument('-p',
                        '--port',
                        default=app.config['DEFAULT_PORT'],
                        type=int)

    args = parser.parse_args()

    app.run(host=args.host, port=args.port)

else:
    print('This script should be run from command line')
