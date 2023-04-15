import os
import boto3
import discord
import paramiko
from discord.ext import commands
from dotenv import load_dotenv
from minestat import MineStat

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='>', intents=intents)
ec2 = boto3.client('ec2')
instance_id = os.getenv('INSTANCE_ID')


async def execute_command(public_ip, command):
    with paramiko.SSHClient() as ssh:
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=public_ip, username='ec2-user',
                    key_filename=os.getenv('KEY_FILENAME'))
        return ssh.exec_command(command)


async def backup_instance(public_ip, ctx):
    stdin, stdout, stderr = await execute_command(public_ip, 'bash /home/ec2-user/backup-server.sh')
    output = stdout.readlines()
    exit_status = stdout.channel.recv_exit_status()

    if exit_status == 0:
        emoji = discord.PartialEmoji(name='✅')
        await ctx.send(f'{emoji}Backup do servidor executado com `sucesso`!')
    else:
        print(output)
        emoji = discord.PartialEmoji(name='❌')
        await ctx.send(f'{emoji}Backup do servidor executado com `falha`!')


async def stop_minecraft_service(public_ip, ctx):
    stdin, stdout, stderr = await execute_command(public_ip, 'sudo systemctl stop minecraft.service')
    output = stdout.readlines()
    exit_status = stdout.channel.recv_exit_status()

    if exit_status == 0:
        await ctx.send('Serviço parado com `sucesso`!')
    else:
        print(output)
        await ctx.send('Serviço parado com `falha`!')


async def start_minecraft_service(public_ip, ctx):
    stdin, stdout, stderr = await execute_command(public_ip, 'sudo systemctl start minecraft.service')
    output = stdout.readlines()
    exit_status = stdout.channel.recv_exit_status()

    if exit_status == 0:
        await ctx.send('Serviço iniciado com `sucesso`!')
    else:
        print(output)
        await ctx.send('Serviço iniciado com `falha`!')


def get_instance_details(instance_id):
    response = ec2.describe_instances(InstanceIds=[instance_id])
    instance = response['Reservations'][0]['Instances'][0]
    return {
        'state': instance['State']['Name'],
        'public_ip': instance['PublicIpAddress']
    }


@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)
@commands.has_any_role('admin', 'moderador')
async def status(ctx):
    await ctx.send('Consultando status do servidor, aguarde...')

    response = ec2.describe_instances(InstanceIds=[instance_id])
    server_state = response['Reservations'][0]['Instances'][0]['State']['Name']
    public_ip = response['Reservations'][0]['Instances'][0]['PublicIpAddress']

    if server_state == 'running':
        mstat = MineStat(public_ip)
        if str(mstat.connection_status) == 'SUCCESS':
            await ctx.send('Status atual do servidor do Minecraft: `{0}`. \nQuantidade atual de jogadores online: `{1}`.'.format(server_state, mstat.current_players))
        else:
            await ctx.send('Status atual do servidor do Minecraft: `{0}`, porém serviço do minecraft se encontra parado, contate o administrador.'.format(server_state))
    else:
        await ctx.send('Status atual do servidor do Minecraft: `{0}`.'.format(server_state))


@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)
@commands.has_any_role('admin', 'moderador')
async def start(ctx):
    instance = get_instance_details(instance_id)
    server_state = instance['state']
    public_ip = instance['public_ip']

    if server_state == 'stopped':
        ec2.start_instances(InstanceIds=[instance_id])
        await ctx.send('Servidor do Minecraft iniciado com sucesso! \n Aguarde alguns instantes até que o serviço do minecraft se inicie.')
    elif server_state == 'running':
        mstat = MineStat(public_ip)
        if str(mstat.connection_status) == 'SUCCESS':
            await ctx.send('Servidor do Minecraft já se encontra iniciado!')
        else:
            await start_minecraft_service(public_ip, ctx)
    else:
        await ctx.send('Estado atual do servidor é inválido, contate o administrador!')


@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)
@commands.has_any_role('admin', 'moderador')
async def stop(ctx):
    instance = get_instance_details(instance_id)
    server_state = instance['state']
    public_ip = instance['public_ip']

    if server_state == 'stopped':
        await ctx.send('Servidor do Minecraft já está desligado!')
    elif server_state == 'running':
        mstat = MineStat(public_ip)
        if '--force' in ctx.message.content:
            ec2.stop_instances(InstanceIds=[instance_id])
            await ctx.send('Servidor do Minecraft desligado forçadamente com sucesso!')
        elif str(mstat.connection_status) == 'SUCCESS':
            if mstat.current_players > 0:
                await ctx.send('Existem players online no momento, para forçar encerramento do servidor envie o comando `>stop --force`.')
            else:
                # ec2.stop_instances(InstanceIds=[instance_id])
                # await ctx.send('Não compensa desligar o servidor por conta do custo do ip elastico com a instancia desligada!')
                await stop_minecraft_service(public_ip, ctx)
    else:
        await ctx.send('Estado atual do servidor é inválido, contate o administrador!')


@bot.command()
@commands.cooldown(1, 60, commands.BucketType.user)
@commands.has_any_role('admin', 'moderador')
async def backup(ctx):
    instance = get_instance_details(instance_id)
    server_state = instance['state']
    public_ip = instance['public_ip']

    if server_state == 'stopped':
        await ctx.send('Servidor do Minecraft está desligado!')
    elif server_state == 'running':
        await ctx.send('Efetuando backup do servidor, isso pode demorar cerca de um minuto...')
        mstat = MineStat(public_ip)
        if '--force' in ctx.message.content:
            await ctx.send('Forçando backup do servidor...')
            await backup_instance(public_ip, ctx)
        elif str(mstat.connection_status) == 'SUCCESS':
            if mstat.current_players > 0:
                await ctx.send('Existem players online no momento, para forçar backup do servidor envie o comando `>backup --force`.')
            else:
                await backup_instance(public_ip, ctx)
        else:
            await backup_instance(public_ip, ctx)
    else:
        await ctx.send('Estado atual do servidor é inválido, contate o administrador!')



bot.run(os.getenv('TOKEN'))
