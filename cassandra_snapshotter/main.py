from collections import defaultdict
from fabric.api import env
import logging
from snapshotting import BackupWorker, RestoreWorker
from snapshotting import Snapshot
from snapshotting import SnapshotCollection
from utils import base_parser


def run_backup(args):
    if args.user:
        env.user = args.user
    env.hosts = sorted(args.hosts.split(','))

    if args.new_snapshot:
        create_snapshot = True
    else:
        existing_snapshot = SnapshotCollection(
            args.aws_access_key_id,
            args.aws_secret_access_key,
            args.s3_base_path,
            args.s3_bucket_name
        ).get_snapshot_for(
            hosts=env.hosts,
            keyspaces=args.keyspaces,
            table=args.table
        )
        create_snapshot = existing_snapshot is None

    worker = BackupWorker(
        aws_access_key_id=args.aws_access_key_id,
        aws_secret_access_key=args.aws_secret_access_key,
        cassandra_data_path=args.cassandra_data_path,
        nodetool_path=args.nodetool_path
    )

    if create_snapshot:
        logging.info('make a new snapshot')
        snapshot = Snapshot(
            base_path=args.s3_base_path,
            s3_bucket=args.s3_bucket_name,
            hosts=env.hosts,
            keyspaces=args.keyspaces,
            table=args.table
        )
        worker.snapshot(snapshot)
    else:
        logging.info('add incrementals to snapshot %s' % existing_snapshot)
        worker.update_snapshot(existing_snapshot)


def list_backups(args):
    snapshots = SnapshotCollection(
        args.aws_access_key_id,
        args.aws_secret_access_key,
        args.s3_base_path,
        args.s3_bucket_name
    )
    path_snapshots = defaultdict(list)

    for snapshot in snapshots:
        base_path = '/'.join(snapshot.base_path.split('/')[:-1])
        path_snapshots[base_path].append(snapshot)

    for path, snapshots in path_snapshots.iteritems():
        print '-----------[%s]-----------' % path
        for snapshot in snapshots:
            print '\t %r hosts:%r keyspaces:%r table:%r' % (snapshot, snapshot.hosts, snapshot.keyspaces, snapshot.table)
        print '------------------------' + '-' * len(path)


def restore_backup(args):
    snapshots = SnapshotCollection(
        args.aws_access_key_id,
        args.aws_secret_access_key,
        args.s3_base_path,
        args.s3_bucket_name
    )

    if args.snapshot_name == 'LATEST':
        snapshot = snapshots.get_latest()
    else:
        snapshot = snapshots.get_snapshot_by_name(args.backup_name)

    worker = RestoreWorker(aws_access_key_id=args.aws_access_key_id,
                           aws_secret_access_key=args.aws_secret_access_key,
                           snapshot=snapshot)

    if args.hosts:
        hosts = args.hosts.split(',')
    else:
        hosts = snapshot.hosts

    target_hosts = args.target_hosts.split(',')

    worker.restore(args.keyspace, args.table, hosts, target_hosts)


def main():

    subparsers = base_parser.add_subparsers(title='subcommands',
                                       dest='subcommand')

    subparsers.add_parser('list', help='list existing backups')

    backup_parser = subparsers.add_parser('backup', help='create a snapshot')

    # snapshot / backup arguments
    backup_parser.add_argument('--hosts',
                               required=True,
                               help='The comma separated list of hosts to snapshot')

    backup_parser.add_argument('--keyspaces',
                               default='',
                               help='The keyspaces to backup (omit to backup all)')

    backup_parser.add_argument('--table',
                               default='',
                               help='The table (column family) to backup')

    backup_parser.add_argument('--cassandra-data-path',
                               default='/var/lib/cassandra/data/',
                               help='cassandra data path.')

    backup_parser.add_argument('--nodetool-path',
                               default='/usr/bin/nodetool',
                               help='nodetool path.')

    backup_parser.add_argument('--user',
                               help='the ssh user to loging on nodes')

    backup_parser.add_argument('--new-snapshot',
                               action='store_true',
                               help='create a new snapshot')

    # restore snapshot arguments
    restore_parser = subparsers.add_parser('restore', help='restores a snapshot')
    restore_parser.add_argument('--snapshot-name',
                                default='LATEST',
                                help='The name (date/time) of the snapshot (and incrementals) to restore')
    restore_parser.add_argument('--keyspace',
                                required=True,
                                help='The keyspace to restore')
    restore_parser.add_argument('--table',
                                default='',
                                help='The table (column family) to restore; leave blank for all')
    restore_parser.add_argument('--hosts',
                                default='',
                                help='Comma separated list of hosts to restore from; leave empty for all')
    restore_parser.add_argument('--target-hosts',
                                required=True,
                                help="The comma separated list of hosts to restore into")

    args = base_parser.parse_args()
    subcommand = args.subcommand

    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    if subcommand == 'backup':
        run_backup(args)
    elif subcommand == 'list':
        list_backups(args)
    elif subcommand == 'restore':
        restore_backup(args)

if __name__ == '__main__':
    main()
