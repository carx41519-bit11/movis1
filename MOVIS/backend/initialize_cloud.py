"""Interactive cloud account setup; no passwords in source or command arguments."""
import argparse
import getpass
import os
from pathlib import Path
from service import Service, Error, password_hash

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',help='Local SQLite file; omit to use DATABASE_URL')
    parser.add_argument('--seed-demo',action='store_true')
    parser.add_argument('--reset-admin-password',metavar='USERNAME')
    args=parser.parse_args()
    if args.db:
        path=Path(args.db).expanduser().resolve();path.parent.mkdir(parents=True,exist_ok=True)
    else:
        path=os.environ.get('DATABASE_URL')
        if not path:raise Error('Provide --db or set DATABASE_URL privately')
    service=Service(path)
    with service.connection() as con:count=con.execute('SELECT count(*) FROM users').fetchone()[0]
    if count and not args.reset_admin_password:
        print('Database already initialized. Existing stock and accounts were preserved.')
        return
    username=args.reset_admin_password or input('New administrator username: ').strip()
    if not username:raise Error('Username is required')
    password=getpass.getpass('Choose a NEW private password (12+ characters): ')
    if len(password)<12 or password=='movis-demo-2026':raise Error('Use a new private password of at least 12 characters')
    if password!=getpass.getpass('Confirm password: '):raise Error('Passwords do not match')
    if args.reset_admin_password:
        with service.connection() as con:
            user=con.execute("SELECT id FROM users WHERE username=? AND role='admin'",(username,)).fetchone()
            if not user:raise Error('Administrator account not found')
            con.execute('UPDATE users SET password=? WHERE id=?',(password_hash(password),user['id']))
            con.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        print('Administrator password updated. Previous sessions revoked.')
    else:
        service.bootstrap(username,password,demo=args.seed_demo)
        print('Cloud administrator initialized. Start the hosted WSGI web app.')

if __name__=='__main__':
    try:main()
    except Error as exc:raise SystemExit(str(exc))
