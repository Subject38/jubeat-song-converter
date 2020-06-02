mergeMemon(){
	local name=$1
  local artist=$2
  local bsc=$3
  local adv=$4
  local ext=$5
  local safe_name=$6
  cd "$safe_name"
	jq -s '.[0]["data"] += (.[1]["data"] + .[2]["data"]) | .[0] | .["metadata"]["song title"] = '"\"$name\""' | .["metadata"]["music path"] = '"\"${safe_name}.ogg\""' | .["metadata"]["album cover path"] = '"\"${safe_name}.png\""" | .metadata.artist = \"$artist\" | .data.BSC.level = $bsc | .data.ADV.level = $adv | .data.EXT.level = $ext"  *.memon > "${safe_name}.memon"
  cd ..
}

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

cat jubeat.tsv | tr -d '\r' | while IFS=$'\t' read -r ID name artist bsc_diff adv_diff ext_diff; do
  ifstools ifs_pack/d${ID:0:-1}/${ID}_msc.ifs;
  
  safe_name=$(echo "$name" | iconv -f utf8 -t eucjp | kakasi -i euc -Ha -Ka -Ja -Ea -ka);
  safe_name=$(echo "$safename" | tr '[<>:"/\|?*]' '_' | sed 's/\.$/_/');
  mkdir "$safe_name" -p;
  eve2memon ${ID}_msc_ifs/bsc.eve "${safe_name}/bsc.memon";
  eve2memon ${ID}_msc_ifs/adv.eve "${safe_name}/adv.memon";
  eve2memon ${ID}_msc_ifs/ext.eve "${safe_name}/ext.memon";
  mergeMemon "$name" "$artist" $bsc_diff $adv_diff $ext_diff "$safe_name";
  rm "${safe_name}/bsc.memon" "${safe_name}/adv.memon" "${safe_name}/ext.memon";
  convertBGM "../${ID}_msc_ifs/bgm.bin" "../${safe_name}/${safe_name}";
  rm -rf ${ID}_msc_ifs;
done
