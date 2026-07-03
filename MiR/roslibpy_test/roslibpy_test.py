import roslibpy


def main():
    client = roslibpy.Ros(host='192.168.1.13', port=9090)
    client.run()
    print('Is ROS connected?', client.is_connected)
    print(client.get_topics())
    print(client.get_services())
    print(client.get_params())
    client.terminate()

if __name__ == '__main__':
    main()