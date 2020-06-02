mergeMemon(){
	local name=$1
  local artist=$2
  local bsc=$3
  local adv=$4
  local ext=$5
  local safe_name=$6
  local version=$7
  cd "$version/$safe_name"
	jq -s '.[0]["data"] += (.[1]["data"] + .[2]["data"]) | .[0] | .["metadata"]["song title"] = '"\"$name\""' | .["metadata"]["music path"] = '"\"${safe_name}.ogg\""" | .metadata.artist = \"$artist\" | .data.BSC.level = $bsc | .data.ADV.level = $adv | .data.EXT.level = $ext"  *.memon > "${safe_name}.memon"
  cd ../..
}
#add this later ' | .["metadata"]["album cover path"] = '"\"${safe_name}.png\""
eve2memon(){
	local input=$1
	local output=$2
  python3 gitadora-customs/memon2eve.py "$input" "$output" -r
}

convertBGM(){
  cd gitadora-customs
  local input=$1
  local output=$2
  python3 wavbintool.py -i "${input}" -o "${output}.wav" -d
  ffmpeg -i "${output}.wav" -c:a libvorbis -aq 4 "${output}.ogg" -nostdin -threads 0
  rm "${output}.wav"
  cd ..
}

cat jubeat2.tsv | tr -d '\r' | while IFS=$'\t' read -r ID name artist bsc_diff adv_diff ext_diff; do
  ifstools ifs_pack/d${ID:0:-1}/${ID}_msc.ifs;
  version=${ID:0:1};
  case $version in 
    1)
    version_name="jubeat"
    ;;
    2)
    version_name="jubeat_ripples"
    ;;
    3)
    version_name="jubeat_coupious"
    ;;
    4)
    version_name="jubeat_saucer"
    ;;
    5)
    version_name="jubeat_saucer_fulfill"
    ;;
    6)
    version_name="jubeat_prop"
    ;;
    7)
    version_name="jubeat_qubell"
    ;;
    8)
    version_name="jubeat_clan"
    ;;
    9)
    version_name="jubeat_festo"
    ;;
    *)
    version_name="invalid"
  esac
  echo 
  safe_name=$(echo "$name" | iconv -f utf8 -t eucjp | kakasi -i euc -Ha -Ka -Ja -Ea -ka | iconv -f eucjp -t ascii);
  safe_name=$(echo "$safe_name" | tr '[<>:"/\|?*]' '_' | sed 's/\.$/_/');
  mkdir "${version_name}/$safe_name" -p;
  eve2memon ${ID}_msc_ifs/bsc.eve "${version_name}/${safe_name}/bsc.memon";
  eve2memon ${ID}_msc_ifs/adv.eve "${version_name}/${safe_name}/adv.memon";
  eve2memon ${ID}_msc_ifs/ext.eve "${version_name}/${safe_name}/ext.memon";
  mergeMemon "$name" "$artist" $bsc_diff $adv_diff $ext_diff "$safe_name" "${version_name}";
  rm "${version_name}/${safe_name}/bsc.memon" "${version_name}/${safe_name}/adv.memon" "${version_name}/${safe_name}/ext.memon";
  convertBGM "../${ID}_msc_ifs/bgm.bin" "../${version_name}/${safe_name}/${safe_name}";
  rm -rf ${ID}_msc_ifs;
done
