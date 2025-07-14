import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Copyright from '../Copyright';
import SessionsChart from './SessionsChart';
import {useEffect, useState} from "react";
// @ts-ignore
import useMqtt from '../../assets/usemqtt';
import type {DataPoint, TopicMap} from '../../assets/helpers';
import {Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow} from "@mui/material";
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {faGithub, faPython, faDocker, faDiscord} from "@fortawesome/free-brands-svg-icons";

import rtdIcon from "../../assets/readthedocs.svg";

export default function MainGrid() {

  const [sent, setSent] = useState<DataPoint[]>([]);
  const [received, setReceived] = useState<DataPoint[]>([]);
  const [bytesIn, setBytesIn] = useState<DataPoint[]>([]);
  const [bytesOut, setBytesOut] = useState<DataPoint[]>([]);
  const [clientsConnected, setClientsConnected] = useState<DataPoint[]>([]);
  const [serverStart, setServerStart] = useState<string>('');
  const [serverUptime, setServerUptime] = useState<string>('');
  const [cpuPercent, setCpuPercent] = useState<DataPoint[]>([]);
  const [memSize, setMemSize] = useState<DataPoint[]>([]);
  const [version, setVersion] = useState<string>('');

  function getRandomInt(min: number, max: number) {
    min = Math.ceil(min);
    max = Math.floor(max);
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  function secondsToDhms(seconds: number) {
    const days = Math.floor(seconds / (24 * 3600));
    seconds %= (24 * 3600);
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const minutes = Math.floor(seconds / 60);
    seconds = seconds % 60;

    return {
      days: days,
      hours: hours,
      minutes: minutes,
      seconds: seconds,
    };
  }

  const mqtt_settings = {
    url: import.meta.env.VITE_MQTT_WS_TYPE + '://' + import.meta.env.VITE_MQTT_WS_HOST + ':' + import.meta.env.VITE_MQTT_WS_PORT, client_id: `web-client-${getRandomInt(1, 100)}`,
      clean: true,
      protocol: 'wss',
      protocolVersion: 4, // MQTT 3.1.1
      wsOptions: {
        protocol: 'mqtt'
      }
  };

  const {mqttSubscribe, isConnected, messageQueue, messageTick} = useMqtt(mqtt_settings);

  useEffect(() => {
    if (isConnected) {
      mqttSubscribe('$SYS/broker/version');
      mqttSubscribe('$SYS/broker/messages/publish/#');
      mqttSubscribe('$SYS/broker/load/bytes/#');
      mqttSubscribe('$SYS/broker/uptime/formatted');
      mqttSubscribe('$SYS/broker/uptime');
      mqttSubscribe('$SYS/broker/clients/connected');
      mqttSubscribe('$SYS/broker/cpu/percent');
      mqttSubscribe('$SYS/broker/heap/size')
    }
  }, [isConnected, mqttSubscribe]);

  const topic_map: TopicMap = {
    '$SYS/broker/messages/publish/sent': {current: sent, update: setSent},
    '$SYS/broker/messages/publish/received': {current: received, update: setReceived},
    '$SYS/broker/load/bytes/received': {current: bytesIn, update: setBytesIn},
    '$SYS/broker/load/bytes/sent': {current: bytesOut, update: setBytesOut},
    '$SYS/broker/clients/connected': {current: clientsConnected, update: setClientsConnected},
    '$SYS/broker/cpu/percent': {current: cpuPercent, update: setCpuPercent},
    '$SYS/broker/heap/size': {current: memSize, update: setMemSize},
  };

  useEffect(() => {

    while (messageQueue.current.length > 0) {
      const payload = messageQueue.current.shift()!;
      try {

        const d = payload.message;

        if(payload.topic in topic_map) {
          const { update } = topic_map[payload.topic];
          const newPoint: DataPoint = {
            time: new Date().toISOString(),
            timestamp: Date.now(),
            value: d
          };
          update(current => [...current, newPoint])
        } else if (payload.topic === '$SYS/broker/uptime/formatted') {
          const dt = new Date(d + "Z");
          setServerStart(dt.toLocaleString());
        } else if (payload.topic === '$SYS/broker/uptime') {
          const {days, hours, minutes, seconds} = secondsToDhms(d);
          setServerUptime(`${days} days, ${hours} hours, ${minutes} minutes, ${seconds} seconds`);
        } else if(payload.topic === '$SYS/broker/version') {
          setVersion(d);
        }
      } catch (e) {
        console.log(e);
      }
    }
  }, [messageTick, messageQueue]);

  return (
    <Box sx={{width: '100%', maxWidth: {sm: '100%', md: '1700px'}}}>
      {/* cards */}

      <Grid
        container
        spacing={2}
        columns={12}
        sx={{mb: (theme) => theme.spacing(2)}}
      >
        <Grid size={{xs: 10, md: 5}}>
          <Typography component="h2" variant="h6" sx={{mb: 2}}>
            Overview
          </Typography>
          <div>
            <p style={{textAlign: 'left'}}>This is <b>test.amqtt.io</b>.</p>
            <p style={{textAlign: 'left'}}>It hosts a publicly available aMQTT server/broker.</p>
            <p style={{textAlign: 'left'}}><a href="http://www.mqtt.org">MQTT</a> is a very lightweight
              protocol that uses a publish/subscribe model. This makes it suitable for "machine to machine"
              messaging such as with low power sensors or mobile devices.
            </p>
            <p style={{textAlign: 'left'}}>For more information: </p>
            <table>
              <tbody>
              <tr>
                <td style={{width: 250}}>
                  <p style={{textAlign: 'left'}}>
                    <FontAwesomeIcon icon={faGithub} size="xl"/> github: <a
                    href="https://github.com/Yakifo/amqtt">Yakifo/amqtt</a>
                  </p>
                  <p style={{textAlign: 'left'}}>
                    <FontAwesomeIcon icon={faPython} size="xl"/> PyPi: <a
                    href="https://pypi.org/project/amqtt/">aMQTT</a>
                  </p>
                  <p style={{textAlign: 'left'}}>
                    <FontAwesomeIcon icon={faDiscord} size="xl"/> Discord: <a
                    href="https://discord.gg/S3sP6dDaF3">aMQTT</a>
                  </p>
                </td>
                <td>
                  <p style={{textAlign: 'left'}}>
                    <img
                      src={rtdIcon}
                      style={{width: 20, verticalAlign: -4}}
                      alt="website logo"
                    />
                    ReadTheDocs: <a href="https://amqtt.readthedocs.io/">aMQTT</a>
                  </p>
                  <p style={{textAlign: 'left'}}>
                    <FontAwesomeIcon icon={faDocker} size="xl"/> DockerHub: <a
                    href="https://hub.docker.com/repositories/amqtt">aMQTT</a>
                  </p>
                  <p>&nbsp;</p>
                </td>
              </tr>
              </tbody>
            </table>


          </div>
        </Grid>
        <Grid size={{xs: 1, md: 1}}></Grid>
        <Grid size={{xs: 12, md: 6}}>
          <Typography component="h2" variant="h6" sx={{mb: 2}}>
            Access
          </Typography>
          <TableContainer component={Paper}>
            <Table sx={{maxWidth: 400}} size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Host</TableCell>
                  <TableCell>test.amqtt.io</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                <TableRow>
                  <TableCell>TCP</TableCell>
                  <TableCell>1883</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>TLS TCP</TableCell>
                  <TableCell>8883</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>Websocket</TableCell>
                  <TableCell>8080</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell>SSL Websocket</TableCell>
                  <TableCell>8443</TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </TableContainer>
          <p style={{textAlign: 'left'}}>
            The purpose of this free MQTT broker at <strong>test.amqtt.io</strong> is to learn about and test the MQTT
            protocol. It
            should not be used in production, development, staging or uat environments. Do not to use it to send any
            sensitive information or personal data into the system as all topics are public. Any illegal use of this
            MQTT broker is strictly forbidden. By using this MQTT broker located at <strong>test.amqtt.io</strong> you
            warrant that you are neither a sanctioned person nor located in a country that is subject to sanctions.
          </p>
        </Grid>
      </Grid>
      <Grid
        container
        spacing={2}
        columns={12}
        sx={{mb: (theme) => theme.spacing(2)}}
      ><Grid size={{xs: 12, md: 12}}>
        <strong>broker</strong> ('{version}') <strong>started at </strong> {serverStart} &nbsp;&nbsp;&nbsp;
        <strong>up for</strong> {serverUptime}
      </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <SessionsChart title={'Sent Messages'} label={''} data={sent} isConnected={isConnected} isPerSecond/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <SessionsChart title={'Received Messages'} label={''} data={received} isConnected={isConnected} isPerSecond/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <SessionsChart title={'Bytes Out'} label={'Bytes'} data={bytesOut} isConnected={isConnected}/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <SessionsChart title={'Bytes In'} label={'Bytes'} data={bytesIn} isConnected={isConnected}/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <SessionsChart title={'Clients Connected'} label={''} data={clientsConnected} isConnected={isConnected}/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <Grid container spacing={2} columns={2}>
            <Grid size={{lg:1}}>
              <SessionsChart title={'CPU'} label={'%'} data={cpuPercent} decimals={2} isConnected={isConnected}/>
            </Grid>
            <Grid size={{lg:1}}>
              <SessionsChart title={'Memory'} label={'MB'} data={memSize} decimals={1} isConnected={isConnected}/>
            </Grid>
          </Grid>
        </Grid>
      </Grid>

      <Grid container spacing={2} columns={12}>
        <Grid size={{xs: 12, lg: 9}}></Grid>
        <Grid size={{xs: 12, lg: 3}}>
          <Stack gap={2} direction={{xs: 'column', sm: 'row', lg: 'column'}}></Stack>
        </Grid>
      </Grid>
      <Copyright sx={{my: 4}}/>
    </Box>
  );
}
