#!/usr/bin/env python3
"""
Permission management smoke test for the music-backend project.
This script backs up users.json, runs several add/remove permission operations
against the users.add_permission / users.remove_permission helpers, prints
results, and restores the original users.json.

Run from the project root: python3 permission_test.py
"""
import shutil
import json
from pathlib import Path
import sys

ROOT = Path(__file__).parent
USERS_PATH = ROOT / 'users.json'
BACKUP_PATH = ROOT / 'users.json.bak'

# Ensure we run from project dir
print('Working directory:', ROOT)

# Backup
if not USERS_PATH.exists():
    print('users.json not found at', USERS_PATH)
    sys.exit(1)
shutil.copy(USERS_PATH, BACKUP_PATH)
print('Backed up users.json -> users.json.bak')

import users
from fastapi import HTTPException

def try_add(actor, target, perm):
    try:
        print(f"ADD: actor={actor} target={target} perm={perm}")
        res = users.add_permission(actor, target, perm)
        print(" -> OK; target perms:", res.get('permissions'))
    except HTTPException as e:
        print(" -> FAIL (HTTPException):", getattr(e, 'detail', str(e)))
    except Exception as e:
        print(" -> FAIL (Exception):", type(e).__name__, str(e))

def try_remove(actor, target, perm):
    try:
        print(f"REMOVE: actor={actor} target={target} perm={perm}")
        res = users.remove_permission(actor, target, perm)
        print(" -> OK; target perms:", res.get('permissions'))
    except HTTPException as e:
        print(" -> FAIL (HTTPException):", getattr(e, 'detail', str(e)))
    except Exception as e:
        print(" -> FAIL (Exception):", type(e).__name__, str(e))

print('\nInitial users.json:')
print(json.dumps(json.load(open(USERS_PATH, 'r')), indent=2, ensure_ascii=False))

# Test 1: dev (user 0) adds superadmin to user 100 -> should succeed (0 has 'dev')
try_add('0', '100', 'superadmin')

# Test 2: music user (100) tries to add admin to 0 -> should fail
try_add('100', '0', 'admin')

# Add temporary user 200 with only 'admin'
data = json.load(open(USERS_PATH, 'r'))
data['users']['200'] = {'name':'Temp Admin','permissions':['admin'],'banned':False,'reason':None}
json.dump(data, open(USERS_PATH, 'w'), indent=4, ensure_ascii=False)
print('\nAdded temp user 200 with admin')
print(json.dumps(json.load(open(USERS_PATH, 'r')), indent=2, ensure_ascii=False))

# Test 3: admin (200) tries to add admin to 100 -> should fail (needs superadmin)
try_add('200', '100', 'admin')

# Test 4: dev (0) adds admin to 100 -> should succeed
try_add('0', '100', 'admin')

# Test 5: dev removes superadmin from 100 -> should succeed
try_remove('0', '100', 'superadmin')

# Cleanup: restore original users.json
shutil.move(BACKUP_PATH, USERS_PATH)
print('\nRestored original users.json')
print('Final users.json:')
print(json.dumps(json.load(open(USERS_PATH, 'r')), indent=2, ensure_ascii=False))
