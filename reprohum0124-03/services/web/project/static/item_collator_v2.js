//https://flask.palletsprojects.com/en/stable/patterns/javascript/

function load_session(session_id, participant_id){

    console.log("initialized");
    const RegSession = {
        session_id: session_id,
        participant_id : participant_id,
        represent : function() {
          return this.session_id + " " + this.participant_id;
        }
      };

    
    window.sessionStorage.setItem('reprohum_data', JSON.stringify(RegSession));
    console.log(window.sessionStorage.reprohum_data);
}



function item_collate(radio1, radio2, radio3, pos_id, item_id, session_id, task_id, participant_id, list_id){

    input_to_memory(radio1, radio2, radio3, pos_id, item_id, session_id, task_id, participant_id, list_id);

    let x = document.getElementById(pos_id);
    x.style.display = 'none';
    //x.parentNode.parentNode.removeChild(x.parentNode);
    x.parentNode.removeChild(x);

    let next_id = Number(pos_id);
    next_id = next_id + 1;
    next_id_str = next_id.toString()

    let next_item = document.getElementById(next_id_str);
    let next_button = next_id_str + "_button";
    let next_timer = next_id_str + "_timer";
    
    next_item.style.display = "block";
    initButton(next_button, next_timer);

}





async function submit_data(radio1, radio2, radio3, pos_id, item_id, session_id, task_id, participant_id, list_id){

    input_to_memory(radio1, radio2, radio3, pos_id, item_id, session_id, task_id, participant_id, list_id);

    let x = document.getElementById(pos_id);
    x.style.dislay = 'noneÄ';
    x.parentNode.removeChild(x);

    let submit_data = window.sessionStorage.getItem("reprohum_data");
    window.sessionStorage.removeItem("reprohum_data");
    window.sessionStorage.clear();

    /*const response = await fetch('/', {
    method: 'POST',
    headers: {
    'Content-Type': 'application/json; charset=utf-8'
    },
    body: submit_data
})*/

  /*fetch("/submit", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            alert("Submission successful! Thank you. Redirecting to prolific for payment");
            console.log("Server Response:", data);
            window.location.href = "{{PROLIFIC_COMPLETION_URL}}";
        })
        .catch(error => {
            alert("Submission failed. Please try again.");
            console.error("Error:", error);
        });*/

fetch('/submit', {
  "method": "POST",
  "redirect": 'follow',
  "headers": {"Content-Type": "application/json"},
  "body": submit_data,
}).then(
  response => {
      if (response.redirected) {
          window.location = response.url;
      } else {
          throw 500;
      }
  }
)

//console.log('status:', response.status)



}




function submit_credentials(session_id, participant_id){

  let input_name = document.getElementById("inputName").value;
  let input_native = document.getElementById("inputNative").value;
  
  let age_i = document.getElementById("inputAge");
  let age = age_i.options[age_i.selectedIndex].value;
  let gen_i = document.getElementById("inputGender");
  let gen = gen_i.options[gen_i.selectedIndex].value;

  country_i = document.getElementById("inputCountry");
  let country = country_i.options[country_i.selectedIndex].value;
  
  prof_i = document.getElementById("inputProf");
  let prof = prof_i.options[prof_i.selectedIndex].value;
  

  console.log(input_name, input_native, age, gen, country, prof, session_id, participant_id);

 
  const credential_data = {
    session_id: session_id,
    prolific_pid: participant_id,
    name:input_name,
    age:age,
    gender:gen,
    country:country,
    native_language:input_native,
    lang_prof:prof
  };

  window.sessionStorage.setItem("credentials", JSON.stringify(credential_data));

  data_to_send = window.sessionStorage.getItem("credentials")
  console.log(data_to_send);
  //console.log("data being sent...")
  //throw 500;
  
fetch('/prepare/', {
"method": "POST",
"redirect": 'follow',
"headers": {"Content-Type": "application/json", charset:"utf-8"},
"body": data_to_send,
}).then(
  response => {
      if (response.redirected) {
        console.log("getting redirected:");
        console.log(response.url);
          window.location = response.url;
      } else {
        console.log("acutally not a redirect");
        window.location = response.url;
      }
  }
)
/*.then(
  response => {
      if (response.redirected) {
          window.location = response.url;
      } else {
          showLoginError();
      }
  }
)*/

//console.log('status:', response.status)



}




function input_to_memory(radio1, radio2, radio3, pos_id, item_id, session_id, task_id, participant_id, list_id){

    if (window.sessionStorage.getItem("reprohum_data") === null) {
      const RegSession = {
        task_id: task_id,
        list_id: list_id,
        session_id: session_id,
        prolific_pid : participant_id,
        represent : function() {
          return this.session_id + " " + this.pprolific_pid;
        }
      };

    console.log("initialized memory");


    
    window.sessionStorage.setItem('reprohum_data', JSON.stringify(RegSession));
      
    }


    radio1_value = document.querySelector('input[name=' + radio1 + ']:checked').value;
    
    radio2_value = document.querySelector('input[name=' + radio2 + ']:checked').value;

    radio3_value = document.querySelector('input[name=' + radio3 + ']:checked').value;

    let this_reprohum_data = JSON.parse(window.sessionStorage.getItem('reprohum_data'));
    console.log(this_reprohum_data);

      if (!this_reprohum_data.session_data){
        
        const item_data = {
            radio1: radio1_value,
            radio2: radio2_value,
            radio3: radio3_value,
            trial_id: item_id,
            session_id: session_id,
            prolific_pid: participant_id
            };
        const this_session_data = {
            [pos_id]: item_data
        }
        this_reprohum_data['session_data'] = this_session_data;
        window.sessionStorage.setItem("reprohum_data", JSON.stringify(this_reprohum_data));

      } else {
        const item_data = {
            radio1: radio1_value,
            radio2: radio2_value,
            radio3: radio3_value,
            trial_id: item_id,
            session_id: session_id,
            prolific_pid: participant_id
            };
        
        this_reprohum_data.session_data[pos_id] = item_data;
        window.sessionStorage.setItem("reprohum_data", JSON.stringify(this_reprohum_data));
      }
      
      console.log(window.sessionStorage.reprohum_data)
    
}



function initButton(button_id, timer_id){
    document.getElementById(button_id).setAttribute('disabled', 'true');
    var fiveMinutes = 20;
    display = document.getElementById(timer_id);
    startTimer(fiveMinutes, display, button_id, timer_id);
}


 function startTimer(duration, display, button_id, timer_id){
    var timer = duration, minutes, seconds;


    var interval = setInterval(function () {
        minutes = parseInt(timer / 60, 10);
        seconds = parseInt(timer % 60, 10);

        minutes = minutes < 10 ? "0" + minutes : minutes;
        seconds = seconds < 10 ? "0" + seconds : seconds;

        display.innerHTML = minutes + ":" + seconds;
        console.log(timer);

        if (--timer < 0) {
            console.log("Modified: Setting button as enabled now!");
            console.log(button_id);
            console.log(timer_id);
            timer = duration;

            document.getElementById(button_id).removeAttribute('disabled');
            document.getElementById(timer_id).style.display = 'none';
            clearInterval(interval);
            }
    }, 1000);
    //var timeout = setTimeout(abortTimer, duration*1.1*1000, interval);
    //clearInterval(interval);
}

