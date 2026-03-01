# ECP2
A Python library for controlling Roku devices via ECP2 WebSocket protocol.

> [!CAUTION]
> Only use this library on Roku devices you trust and only use SSDP discovery on networks you trust. I use the Python XML library, which generally should not create issues but please see the [security](https://docs.python.org/3/library/xml.html#xml-security) section of their docs for specific details. XML is parsed during both regular usage and SSDP discovery.

## Short Backstory

Last year sometime I saw a post on a Discord server where someone was remotely controlling their TV with an API it exposed, and I got curious and found out the Roku we had at our house also exposed an API. I tried to use this but it had a lot of limitations that didn't exist in the mobile app, so I dug deeper, creating a WireShark capture between my phone and the TV and found a WebSocket protocol that controlled the TV virtually without limits or safeguards. I decided to make a library out of it for future people to use and used this to create an unstoppable Rickroll program that prevents the TV from turning off, lowering volume, and (less tested) navigating away from the video. That code is attached to the library for anyone interested to see usage / an example.

It is unlikely I go back to the code much because after moving house we no longer have that TV so I can't test new code. Documentation may be added but honestly the library is pretty small and I wouldn't be able to add much more of value than you can find in the code and example.

## Credits

Credit for finding the challenge authentication key goes to [@attain-squiggly-zeppelin](https://github.com/attain-squiggly-zeppelin) in [this GitHub issue thread](https://github.com/home-assistant/core/issues/83819). I know basically nothing about reverse engineering APKs so could not have done this without you. Thank you!
