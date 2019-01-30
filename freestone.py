#!/usr/bin/python

import os
import pathlib

import click
import sh


shfg = sh(_fg=True)


@click.command()
@click.option('--spec',                     help='spec file path')
@click.option('--sourcedir',                help='sources directory',            default='.')   # noqa
@click.option('--define',    'definitions', help='define a macro',               multiple=True) # noqa
@click.option('--with',      'withs',       help='enable configuration option',  multiple=True) # noqa
@click.option('--without',   'withouts',    help='disable configuration option', multiple=True) # noqa
@click.option('--repo',      'repos',       help='add repo',                     multiple=True) # noqa
@click.option('--workspace', 'workspace',   help='working directory',            default='.')   # noqa
def main(spec, sourcedir, definitions, withs, withouts, repos, workspace):

    # privileged commands
    if os.geteuid() == 0:
        yum = shfg.yum
        yum_builddep = shfg.yum_builddep
        yum_config_manager = shfg.yum_config_manager
    else:
        yum = shfg.sudo.yum
        yum_builddep = shfg.sudo.bake('yum-builddep')
        yum_config_manager = shfg.sudo.bake('yum-config-manager')

    # workspace
    workspace = pathlib.Path(workspace).absolute()
    if not workspace.exists():
        raise SystemExit('workspace {0} does not exist'.format(workspace))

    # topdir
    topdir = workspace / 'rpmbuild'

    # spec
    if spec:
        spec = pathlib.Path(spec).absolute()
        if not spec.exists():
            raise SystemExit('spec file {0} does not exist'.format(spec))
    else:
        try:
            [spec] = workspace.rglob('*.spec')
        except ValueError:
            # found zero or more than one spec file
            raise SystemExit(
                'unable to guess spec file path, specify it with `--spec`'
            )

    # sourcedir
    sourcedir = pathlib.Path(sourcedir).absolute()
    if not sourcedir.exists():
        raise SystemExit('sourcedir {0} does not exist'.format(sourcedir))

    # macro definitions
    definitions = list(definitions)
    definitions.extend(
        [
            '_topdir {0}'.format(topdir),
            '_sourcedir {0}'.format(sourcedir),
            '_specdir {0}'.format(spec.parent)
        ]
    )

    # repos
    if repos:
        click.secho('\n==> add repos\n')
        for repo in repos:
            yum_config_manager('--add-repo', repo)

    # build group and tools
    click.secho('\n==> install build group and tools\n')
    yum('--assumeyes', 'install', '@buildsys-build', 'rpmdevtools')

    # rpmbuild setup
    rpmbuild = shfg.rpmbuild
    for definition in definitions:
        rpmbuild = rpmbuild.bake('--define', definition)
    for with_ in withs:
        rpmbuild = rpmbuild.bake('--with', with_)
    for without in withouts:
        rpmbuild = rpmbuild.bake('--without', without)

    # sources
    click.secho('\n==> get sources\n')
    shfg.spectool('--get-files', '--directory', sourcedir, spec)

    # srpm
    click.secho('\n==> build SRPM\n')
    rpmbuild('-bs', spec)
    [srpm_file] = (topdir / 'SRPMS').rglob('*.src.rpm')

    # build requirements
    click.secho('\n==> install build requirements\n')
    yum_builddep('--assumeyes', srpm_file)

    # rpms
    click.secho('\n==> build RPMs\n')
    rpmbuild('-bb', spec)

    # move srpm and rpms to workspace
    srpm_file.rename(workspace / srpm_file.name)
    for rpm_file in (topdir / 'RPMS').rglob('*.rpm'):
        rpm_file.rename(workspace / rpm_file.name)

    # clean up
    shfg.rm('-r', topdir)


if __name__ == '__main__':
    main()
