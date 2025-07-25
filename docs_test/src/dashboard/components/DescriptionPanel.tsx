import Grid from "@mui/material/Grid";
import Typography from "@mui/material/Typography";
import {FontAwesomeIcon} from "@fortawesome/react-fontawesome";
import {faDiscord, faDocker, faGithub, faPython} from "@fortawesome/free-brands-svg-icons";
import rtdIcon from "../../assets/readthedocs.svg";
import {Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow} from "@mui/material";


export default function DescriptionPanel() {
  return <>
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
  </>
}