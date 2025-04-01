import willump
import json
import asyncio
import logging




async def main():
    global wllp
    wllp = await willump.start()

    async def default_message_handler(data):
        print(data['eventType'] + ' ' + data['uri'])

    async def printing_listener(data):
        print(json.dumps(data, indent=4, sort_keys=True))

    ################
    #
    # #Uncomment this block to print /help and see what it provides
    # resp_data = await wllp.request('get', '/help')
    # resp_json = await resp_data.json()
    # print(json.dumps(resp_json, indent=4, sort_keys=True))
    #				#use resp_json['events'] to see only the names of events
    ################

    # creates a subscription to the server event OnJsonApiEvent (which is all Json updates)
    all_events_subscription = await wllp.subscribe(
        'OnJsonApiEvent', default_handler=None)
    # let's add an endpoint filter, and print when we get messages from this endpoint with our printing listener
    wllp.subscription_filter_endpoint(
        all_events_subscription, 'lol-lobby-team-builder/champ-select/v1',
        handler=default_message_handler)

    while True:
        await asyncio.sleep(10)


if __name__ == '__main__':
    # logging.getLogger().setLevel(level=logging.DEBUG)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(wllp.close())
        print()
