import click
import boto3

@click.command()
@click.option('--setup-ssh', is_flag=True, help='Setup SSH by filling authorized_keys file from aws system manager')
def main(setup_ssh):
    if setup_ssh:
        print('Setting up SSH')
        ssm = boto3.client('ssm')
        # test_value = ssm.get_parameter(Name='/test/helloworld')
        # print(test_value)
        ssh_pub_cloud01 = ssm.get_parameter(Name='/sshkey/cloud/cloudNode01/id_rsa')
        print(ssh_pub_cloud01)
        ssh_pub_login = ssm.get_parameter(Name='/sshkey/onprem/loginNode/id_rsa')
        print(ssh_pub_login)

        # TODO: write ssh_pub_cloud01 to authorized_keys file on loginNode
        # TODO: write ssh_pub_login to authorized_keys file on on prem side all worker nodes


    else:
        print('Not setting up SSH')

if __name__ == '__main__':
    main()