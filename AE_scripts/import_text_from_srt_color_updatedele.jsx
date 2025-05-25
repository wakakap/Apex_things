{
    var comp = app.project.activeItem;  // Get the current composition
    if (comp && comp instanceof CompItem) {
        var file = File.openDialog("Select SRT File", "*.srt");
        if (file) {
            file.open("r");
            var srtText = file.read();
            file.close();

            var regex = /(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n{2,}|\n*$)/g;
            var matches = [];
            var match;
            while ((match = regex.exec(srtText)) !== null) {
                matches.push(match);
            }

            // Get the topmost layer in the composition
            var topLayer = comp.layers[1];
            for (var i = 0; i < matches.length; i++) {
                var text = matches[i][4];  // Get text from SRT file
                var startTime = matches[i][2];
                var endTime = matches[i][3];
                
                // Convert time strings to seconds
                var startSeconds = timeToSeconds(startTime);
                var endSeconds = timeToSeconds(endTime);

                // Duplicate the top layer
                var newLayer = topLayer.duplicate();
                newLayer.name = "SRT Text " + (i + 1);

                // Set layer start and end times
                newLayer.startTime = startSeconds;
                newLayer.outPoint = endSeconds;

                // Modify text properties
                var textProp = newLayer.property("Source Text");
                var textDocument = textProp.value;
                textDocument.text = text;

                var firstChar = text[0];

                // 检查是否为特殊震动符号
                var needsShake = false;
                if (firstChar === "!") {
                    needsShake = true;
                    text = text.substring(1); // 移除开头的 "!"
                }
                var headtwo = text.substring(0, 2);;
                // 修改switch部分
                switch (headtwo) {
                    case 'r:':
                        textDocument.strokeColor = [0.2, 0.4, 0.7]; // 柔和的蓝色
                        text = text.substring(2);
                        break;
                    // case 's:':
                    //     textDocument.strokeColor = [0.59, 0.59, 0.06]; // 柔和的黄色
                    //     text = text.substring(2);
                    //     break;
                    // case 't:':
                    //     textDocument.strokeColor = [0.6, 0.85, 1]; // 稍微偏白的浅蓝色
                    //     text = text.substring(2);
                    //     break;
                    // case 'w:':
                    //     textDocument.strokeColor = [0.7, 0.3, 0.3]; // 偏粉的暗红色
                    //     text = text.substring(2);
                    //     break;
                    // case 'e:':
                    //     textDocument.strokeColor = [0.5, 0.7, 0.5]; // 稍微偏白的浅绿色
                    //     text = text.substring(2);
                    //     break;
                    // case 'k:':
                    //     textDocument.strokeColor = [0.7, 0.6, 0.3]; // 柔和的橙色
                    //     text = text.substring(2);
                    //     break;
                    case 'g:':
                        textDocument.strokeColor = [0.11, 0.54, 0.11]; // 柔和的绿色
                        text = text.substring(2);
                        break;
                    // case 'm:':
                    //     textDocument.strokeColor = [0.31, 0.09, 0.17];
                    //     text = text.substring(2);
                    //     break;    
                    default:
                        // textDocument.strokeColor = [1, 1, 1]; // 白色保持不变
                        textDocument.strokeColor = [0.31, 0.09, 0.17]; // Custom color for 'm'
                        break;
                }
                textDocument.text = text;
                textProp.setValue(textDocument);

                // 添加震动表达式（如果需要）
                if (needsShake) {
                    var positionProp = newLayer.property("Position");
                    var expression = 
                        "if (time >= " + startSeconds.toFixed(3) + " && time <= " + (startSeconds + 1).toFixed(3) + ") {\n" +
                        "  freq = 8;\n" +
                        "  amp = 10;\n" +
                        "  decay = 4;\n" +
                        "  t = time - " + startSeconds.toFixed(3) + ";\n" +
                        "  value + [Math.sin(freq * t * 2 * Math.PI), Math.cos(freq * t * 2 * Math.PI)] * amp * Math.exp(-decay * t);\n" +
                        "} else {\n" +
                        "  value;\n" +
                        "}";
                    positionProp.expression = expression;
                }
            }
            alert("SRT file processed successfully!");
        }
    } else {
        alert("Please select a composition.");
    }

    // Helper function: convert time string to seconds
    function timeToSeconds(timeStr) {
        var parts = timeStr.split(':');
        var hours = parseInt(parts[0], 10);
        var minutes = parseInt(parts[1], 10);
        var seconds = parseFloat(parts[2].replace(',', '.'));
        return hours * 3600 + minutes * 60 + seconds;
    }
}
