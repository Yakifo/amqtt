import CountUp from "react-countup";


const byte_units = [
  'Bytes',
  'KB',
  'MB',
  'GB',
  'TB'
]

const update_time = 5;

export function ByteCounter(props: any) {

  let start = props.start;
  let end = props.end;
  if(end - start < 200){
  return <CountUp
    start={start}
    end={end}
    duration={update_time}/>
  }

  let unit = byte_units[0];
  for (let i = 0; i < byte_units.length; i++) {

    if( start > 1_000) {
      start = start / 1000;
      end = end / 1000;
      unit = byte_units[i+1];
    }
  }

  return <CountUp
    start={start}
    end={end}
    suffix={" " + unit}
    decimals={2}
    duration={update_time}/>
}

export function StandardCounter(props: any) {

  return <CountUp
    start={props.start}
    end={props.end}
    duration={update_time}/>
}