import asana

resources = {
    'workspaces':  {
        '_keys' : ('workspace', 'organization'),
        '_fields': ('id', 'name'),
        'teams': {
            '_keys': ('team',),
            '__call__': 'find_by_organization',
            '_fields': ('id', 'name'),
            'users': {
                '__call__':  'find_by_workspace',
                '_fields': ('id', 'name', 'email'),
            },
            'projects': {
                '_keys': ('project_id',  ),
                '__call__': 'find_by_team',
                '_fields': ('id', 'name', 'due_date', 'created_at', 'modified_at', 'archived', 'public', 'notes',
                            'owner.name',
                            'members.name',
                            'followers.name',
                            'workspace.name',
                            'team.name'),
                'tasks': {
                    '__call__': 'find_by_project',
                    '_keys': ('task',),
                    '_fields': ('id', 'name', 'assignee.name', 'created_at', 'completed', 'due_on',
                                'followers.name', 'notes', 'memberships.project.name', 'memberships.section.name',
                                'tags.name', 'parent.name'),
                    'stories': {
                        '__call__': 'find_by_task',
                        '_fields': ('id', 'created_at', 'created_by.name', 'text', 'target.name', 'type')
                    },
                    'attachments': {
                        '__call__': 'find_by_task',
                        '_fields': ('id', 'created_at', 'view_url', 'host', 'name', 'parent.name')

                    }
                }
            }
        }
    }
}


from pprint import pprint
import copy
import json
import os
import urllib2

client = asana.Client.access_token('0/b4001d4abd47fab6953e53d9f7e0995b')

def expand_resource(resource, contents, **parent_resources):
    output = []
    call = contents.get('__call__', 'find_all')
    client_field = getattr(client, resource)
    gen = getattr(client_field, call)(fields=contents['_fields'], **parent_resources)
    for i, asana_object in enumerate(gen):
        if i > MAX:
            break
        print 'expanding {}'.format(resource)
        pprint(asana_object)
        object_out = asana_object

        sub_resources = {r:c for r, c in contents.items() if r[0] != '_'}

        parents = copy.deepcopy(parent_resources)
        if '_keys' in contents:
            for name in contents['_keys']:
                parents[name] = object_out['id']

        for sub_resource, sub_contents in sub_resources.items():
            object_out[sub_resource] = expand_resource(sub_resource, sub_contents, **parents)
        output.append(object_out)
    return output

def fetch_attachments(client, workspaces, folder):
    for workspace in workspaces:
        teams = workspace['teams']
        for team in teams:
            projects = team.get('projects', [])
            for project in projects:
                tasks = project.get('tasks', [])
                for task in tasks:
                    attachments = task.get('attachments', [])
                    for attachment in attachments:
                        if attachment['host'] == 'asana':
                            filename = os.path.join(folder, str(attachment['id']) + '.' + attachment['name'])
                            url = client.attachments.find_by_id(attachment['id'], fields='download_url')['download_url']

                            response = urllib2.urlopen(url)
                            open(filename, 'w').write(response.read())


workspaces = expand_resource('workspaces', resources['workspaces'])
json.dump(workspaces, open('test_output.json', 'w'), indent=2)
if not os.path.exists('attachments'):
    os.mkdir('attachments')
fetch_attachments(client, workspaces, 'attachments')

pprint(workspaces)
