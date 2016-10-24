import asana
from pprint import pprint
import copy
import json
import os
import urllib2
import traceback
import time
import logging

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
logger = logging.getLogger('asana');

ACCESS_TOKEN = '0/a88c38a3cb10a9ecad58fe22cf239289'

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

flat_resource_file = 'resources_by_id.json'
save_at = 200


def index_resources():

    start_time = time.time()
    
    print 'loading...'
    if os.path.exists(flat_resource_file):
        resources_by_id = json.load(open(flat_resource_file))
    else:
        resources_by_id = {}
    print 'loaded'
    resource_gen = expand_resource('workspaces', resources['workspaces'], resources_by_id)
    resource_gen.send(None)
    resource = None
    try:
        i=0
        while True:
            resource = resource_gen.send(resources_by_id)
            if isinstance(resource, dict):
                if str(resource['id']) not in resources_by_id:
                    resources_by_id[str(resource['id'])] = resource
                    i += 1
                    if i % save_at == 0:
                        loger.info('DUMPING!')
                        logger.info('Elapsed time at {}: {} minutes'.format(i, (time.time()-start_time)/60.))
                        dump_start = time.time()
                        json.dump(resources_by_id, open(flat_resource_file, 'w'), indent=2)
                        logger.info('JSON dump took {} seconds'.format(time.time()-dump_start))
    except StopIteration:
        return resource


client = asana.Client.access_token(ACCESS_TOKEN)
 
def expand_resource(resource, contents, resources_by_id, **parent_resources):
    output = []
    call = contents.get('__call__', 'find_all')
    client_field = getattr(client, resource)
    while True:
        try:
            gen = getattr(client_field, call)(fields=contents['_fields'], **parent_resources)
            for i, asana_object in enumerate(gen):

                object_out = asana_object

                if str(object_out['id']) in resources_by_id:
                    try:
                        logger.info('SKIPPING {}: {}'.format(resource, object_out['name']))
                    except Exception:
                        logger.info('Skipping {}: {}'.format(resource, object_out['id']))
                    object_out = resources_by_id[str(object_out['id'])]
                    output.append(object_out)
                    continue

                #print 'expanding {}'.format(resource)
                #pprint(asana_object)

                sub_resources = {r:c for r, c in contents.items() if r[0] != '_'}

                parents = copy.deepcopy(parent_resources)
                if '_keys' in contents:
                    for name in contents['_keys']:
                        parents[name] = object_out['id']

                for sub_resource, sub_contents in sub_resources.items():
                    resource_gen = expand_resource(sub_resource, sub_contents, resources_by_id, **parents)
                    resource_gen.send(None)
                    inner_resource = None
                    try:
                        while True:
                            inner_resource = resource_gen.send(resources_by_id)
                            resources_by_id = yield inner_resource
                    except StopIteration: pass
                    object_out[sub_resource] = inner_resource
                yield object_out
                output.append(object_out)
            yield output
            break
        except Exception as e:
            traceback.print_exc()
            logger.error('ERROR: {}'.format(e))
            logger.info('Retrying...')

def fetch_attachments(client, workspaces, folder):
    i=0
    start_time = time.time()
    for workspace in workspaces:
        teams = workspace['teams'] or []
        for team in teams:
            projects = team.get('projects', []) or []
            for project in projects:
                tasks = project.get('tasks', []) or [] 
                for task in tasks:
                    attachments = task.get('attachments', []) or []
                    for attachment in attachments:
                        if attachment['host'] == 'asana':
                            i+=1
                            if i % 200 == 0:
                                logger.info('{} attachments done at {} minutes'.format(i, (time.time()-start_time)/60.))
                            try:
                                filename = os.path.join(folder, str(attachment['id']) + '.' + attachment['name'])
                                if os.path.exists(filename):
                                    continue
                                url = client.attachments.find_by_id(attachment['id'], fields='download_url')['download_url']

                                response = urllib2.urlopen(url)
                                open(filename, 'w').write(response.read())
                            except:
                                traceback.print_exc()

def create_summary(workspaces, summary_file):
    output = {}
    for workspace in workspaces:
        workspace_out = {}
        teams = workspace['teams'] or []
        for team in teams:
            projects = team.get('projects', []) or []
            team_out = [project['name'] for project in projects]
            workspace_out[team['name']] = team_out
        output[workspace['name']] = workspace_out
    json.dump(output, open(summary_file,'w'), indent=2, sort_keys=True)


if __name__ == '__main__':

    start_time = time.time()
    logger.info("Starting export.")
    workspaces = index_resources()
    json.dump(workspaces, open('workspaces.json', 'w'), indent=2, sort_keys=True)
    logger.info("finished Json export at {} minutes. Fetching attachments".format((time.time()-start_time)/60.))
    if not os.path.exists('attachments'):
        os.mkdir('attachments')
    fetch_attachments(client, workspaces, 'attachments')
    logger.info("attachments fetched at {} minutes.".format((time.time()-start_time)/60.))
    logger.info("creating summary")
    create_summary(workspaces, 'workspace_summary.json')
